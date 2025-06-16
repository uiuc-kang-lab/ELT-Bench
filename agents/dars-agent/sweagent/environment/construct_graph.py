#!/root/miniconda3/envs/aider/bin/python

import colorsys
import argparse
import os
import random
import re
import warnings
from collections import namedtuple
from pathlib import Path
import builtins
import inspect
import networkx as nx
from grep_ast import filename_to_lang
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token
from pygments.util import ClassNotFound
from tqdm import tqdm
import ast
import pickle
import json
from utils_codegraph import create_structure
import concurrent.futures

# tree_sitter is throwing a FutureWarning
warnings.simplefilter("ignore", category=FutureWarning)
from tree_sitter_languages import get_language, get_parser

Tag = namedtuple("Tag", "rel_fname fname line name kind category info".split())


def get_mtime(fname):
    try:
        return os.path.getmtime(fname)
    except FileNotFoundError:
        print(f"File not found error: {fname}")
        return None


def get_tags_raw(fname, rel_fname, structure):
    ref_fname_lst = rel_fname.split('/')
    s = structure
    for fname_part in ref_fname_lst:
        s = s.get(fname_part, {})
    structure_classes = {item['name']: item for item in s.get('classes', [])}
    structure_functions = {item['name']: item for item in s.get('functions', [])}
    structure_class_methods = dict()
    for cls in s.get('classes', []):
        for item in cls.get('methods', []):
            structure_class_methods[item['name']] = item
    structure_all_funcs = {**structure_functions, **structure_class_methods}

    lang = filename_to_lang(fname)
    if not lang:
        return
    language = get_language(lang)
    parser = get_parser(lang)

    # Load the tags queries
    query_scm = """
    (class_definition
    name: (identifier) @name.definition.class) @definition.class

    (function_definition
    name: (identifier) @name.definition.function) @definition.function

    (call
    function: [
        (identifier) @name.reference.call
        (attribute
            attribute: (identifier) @name.reference.call)
    ]) @reference.call
    """

    with open(str(fname), "r", encoding='utf-8') as f:
        code = f.read()
    with open(str(fname), "r", encoding='utf-8') as f:
        codelines = f.readlines()

    # Hard-coded edge cases
    code = code.replace('\ufeff', '')
    code = code.replace('constants.False', '_False')
    code = code.replace('constants.True', '_True')
    code = code.replace("False", "_False")
    code = code.replace("True", "_True")
    code = code.replace("DOMAIN\\username", "DOMAIN\\\\username")
    code = code.replace("Error, ", "Error as ")
    code = code.replace('Exception, ', 'Exception as ')
    code = code.replace("print ", "yield ")
    pattern = r'except\s+\(([^,]+)\s+as\s+([^)]+)\):'
    code = re.sub(pattern, r'except (\1, \2):', code)
    code = code.replace("raise AttributeError as aname", "raise AttributeError")

    if not code:
        return
    tree = parser.parse(bytes(code, "utf-8"))
    try:
        tree_ast = ast.parse(code)
    except:
        tree_ast = None

    # Functions from third-party libs or default libs
    try:
        std_funcs, std_libs = std_proj_funcs(code, fname)
    except:
        std_funcs, std_libs = [], []

    # Functions from builtins
    builtins_funs = [name for name in dir(builtins)]
    builtins_funs += dir(list)
    builtins_funs += dir(dict)
    builtins_funs += dir(set)
    builtins_funs += dir(str)
    builtins_funs += dir(tuple)

    # Run the tags queries
    query = language.query(query_scm)
    captures = query.captures(tree.root_node)
    captures = list(captures)

    saw = set()
    for node, tag in captures:
        if tag.startswith("name.definition."):
            kind = "def"
        elif tag.startswith("name.reference."):
            kind = "ref"
        else:
            continue

        saw.add(kind)
        cur_cdl = codelines[node.start_point[0]]
        category = 'class' if 'class ' in cur_cdl else 'function'
        tag_name = node.text.decode("utf-8")

        # We only want to consider project-dependent functions
        if tag_name in std_funcs:
            continue
        elif tag_name in std_libs:
            continue
        elif tag_name in builtins_funs:
            continue

        if category == 'class':
            if tag_name in structure_classes:
                class_functions = [item['name'] for item in structure_classes[tag_name]['methods']]
                if kind == 'def':
                    line_nums = [structure_classes[tag_name]['start_line'], structure_classes[tag_name]['end_line']]
                else:
                    line_nums = [node.start_point[0], node.end_point[0]]
                result = Tag(
                    rel_fname=rel_fname,
                    fname=fname,
                    name=tag_name,
                    kind=kind,
                    category=category,
                    info='\n'.join(class_functions),  # list unhashable, use string instead
                    line=line_nums,
                )
            else:
                # If the class is not in structure_classes, we'll create a basic Tag
                result = Tag(
                    rel_fname=rel_fname,
                    fname=fname,
                    name=tag_name,
                    kind=kind,
                    category=category,
                    info="Class not found in structure",
                    line=[node.start_point[0], node.end_point[0]],
                )

        elif category == 'function':
            if kind == 'def':
                if tag_name in structure_all_funcs:
                    cur_cdl = '\n'.join(structure_all_funcs[tag_name]['text'])
                    line_nums = [structure_all_funcs[tag_name]['start_line'], structure_all_funcs[tag_name]['end_line']]
                else:
                    cur_cdl = "Function definition not found in structure"
                    line_nums = [node.start_point[0], node.end_point[0]]
            else:
                line_nums = [node.start_point[0], node.end_point[0]]
                cur_cdl = "Function reference"

            result = Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=tag_name,
                kind=kind,
                category=category,
                info=cur_cdl,
                line=line_nums,
            )

        yield result

    if "ref" in saw:
        return
    if "def" not in saw:
        return

    # We saw defs without any refs
    # Some tags files only provide defs (cpp, for example)
    # Use pygments to backfill refs
    try:
        lexer = guess_lexer_for_filename(fname, code)
    except ClassNotFound:
        return

    tokens = list(lexer.get_tokens(code))
    tokens = [token[1] for token in tokens if token[0] in Token.Name]

    for token in tokens:
        yield Tag(
            rel_fname=rel_fname,
            fname=fname,
            name=token,
            kind="ref",
            line=-1,
            category='function',
            info='none',
        )


def std_proj_funcs(code, fname):
    """
    Analyze the import part of a Python file.
    Input: code for fname
    Output: [standard functions], [standard libraries]
    """
    std_libs = []
    std_funcs = []
    tree = ast.parse(code)
    codelines = code.split('\n')

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Identify the import statement
            import_statement = codelines[node.lineno - 1]
            for alias in node.names:
                import_name = alias.name.split('.')[0]
                if import_name in fname:
                    continue
                else:
                    # Execute the import statement to find callable functions
                    import_statement = import_statement.strip()
                    try:
                        exec(import_statement)
                    except:
                        continue
                    std_libs.append(alias.name)
                    eval_name = alias.name if alias.asname is None else alias.asname
                    std_funcs.extend([name for name, member in inspect.getmembers(eval(eval_name)) if callable(member)])

        if isinstance(node, ast.ImportFrom):
            # Execute the import statement
            import_statement = codelines[node.lineno - 1]
            if node.module is None:
                continue
            module_name = node.module.split('.')[0]
            if module_name in fname:
                continue
            else:
                # Handle imports with parentheses
                if "(" in import_statement:
                    for ln in range(node.lineno - 1, len(codelines)):
                        if ")" in codelines[ln]:
                            code_num = ln
                            break
                    import_statement = '\n'.join(codelines[node.lineno - 1:code_num + 1])
                import_statement = import_statement.strip()
                try:
                    exec(import_statement)
                except:
                    continue
                for alias in node.names:
                    std_libs.append(alias.name)
                    eval_name = alias.name if alias.asname is None else alias.asname
                    if eval_name == "*":
                        continue
                    std_funcs.extend([name for name, member in inspect.getmembers(eval(eval_name)) if callable(member)])
    return std_funcs, std_libs


def get_tags(fname, rel_fname, structure):
    file_mtime = get_mtime(fname)
    if file_mtime is None:
        return []
    data = list(get_tags_raw(fname, rel_fname, structure))
    return data


def process_file_wrapper(args):
    fname, rel_fname, structure = args
    tags = get_tags(fname, rel_fname, structure)
    return tags


class CodeGraph:

    def __init__(
        self,
        map_tokens=1024,
        root=None,
        main_model=None,
        io=None,
        repo_content_prefix=None,
        verbose=False,
        max_context_window=None,
    ):
        self.verbose = verbose

        if not root:
            root = os.getcwd()
        self.root = root

        self.max_map_tokens = map_tokens
        self.max_context_window = max_context_window

        self.repo_content_prefix = repo_content_prefix
        self.structure = create_structure(self.root)

    def get_code_graph(self, other_files, mentioned_fnames=None):
        if self.max_map_tokens <= 0:
            return
        if not other_files:
            return
        if not mentioned_fnames:
            mentioned_fnames = set()

        max_map_tokens = self.max_map_tokens

        # With no files in the chat, give a bigger view of the entire repo
        MUL = 16
        padding = 4096
        if max_map_tokens and self.max_context_window:
            target = min(max_map_tokens * MUL, self.max_context_window - padding)
        else:
            target = 0

        tags = self.get_tag_files(other_files, mentioned_fnames)
        code_graph = self.tag_to_graph(tags)

        return tags, code_graph

    def get_tag_files(self, other_files, mentioned_fnames=None):
        try:
            tags = self.get_ranked_tags(other_files, mentioned_fnames)
            return tags
        except RecursionError:
            print("Disabling code graph, git repo too large?")
            self.max_map_tokens = 0
            return

    def tag_to_graph(self, tags):

        G = nx.MultiDiGraph()
        for tag in tags:
            G.add_node(tag.name, category=tag.category, info=tag.info, fname=tag.fname, line=tag.line, kind=tag.kind)

        for tag in tags:
            if tag.category == 'class':
                class_funcs = tag.info.split('\n')
                for f in class_funcs:
                    G.add_edge(tag.name, f.strip())

        tags_ref = [tag for tag in tags if tag.kind == 'ref']
        tags_def = [tag for tag in tags if tag.kind == 'def']
        for tag_ref in tags_ref:
            for tag_def in tags_def:
                if tag_ref.name == tag_def.name:
                    G.add_edge(tag_ref.name, tag_def.name)
        return G

    def get_rel_fname(self, fname):
        return os.path.relpath(fname, self.root)

    def get_ranked_tags(self, other_fnames, mentioned_fnames):
        tags_of_files = []

        fnames = set(other_fnames)
        fnames = sorted(fnames)

        args = []
        for fname in fnames:
            if not Path(fname).is_file():
                if fname not in self.warned_files:
                    if Path(fname).exists():
                        print(f"Code graph can't include {fname}, it is not a normal file")
                    else:
                        print(f"Code graph can't include {fname}, it no longer exists")
                    self.warned_files.add(fname)
                continue

            rel_fname = self.get_rel_fname(fname)
            args.append((fname, rel_fname, self.structure))

        with concurrent.futures.ProcessPoolExecutor(max_workers=32) as executor:
            results = list(tqdm(executor.map(process_file_wrapper, args), total=len(args)))

        for tags in results:
            tags_of_files.extend(tags)

        return tags_of_files

    def find_src_files(self, directory):
        if not os.path.isdir(directory):
            return [directory]

        src_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                src_files.append(os.path.join(root, file))
        return src_files

    def find_files(self, dir):
        chat_fnames = []

        for fname in dir:
            if Path(fname).is_dir():
                chat_fnames += self.find_src_files(fname)
            else:
                chat_fnames.append(fname)

        chat_fnames_new = []
        for item in chat_fnames:
            if not item.endswith('.py'):
                continue
            else:
                chat_fnames_new.append(item)

        return chat_fnames_new


def get_random_color():
    hue = random.random()
    r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue, 1, 0.75)]
    res = f"#{r:02x}{g:02x}{b:02x}"
    return res


def main():
    parser = argparse.ArgumentParser(description="Generate code graph for a repository")
    parser.add_argument("--repo_dir", default=None, help="Path to the repository directory")
    parser.add_argument("--output_dir", default=None, help="Directory to save output files")
    args = parser.parse_args()

    repo_dir = args.repo_dir or os.getcwd()
    output_dir = args.output_dir or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    graph_file = os.path.join(output_dir, 'graph.pkl')
    tags_file = os.path.join(output_dir, 'tags.json')

    if os.path.exists(graph_file) and os.path.exists(tags_file):
        print(f"Graph and tags files already exist in {output_dir}. Skipping generation.")
        return

    code_graph = CodeGraph(root=repo_dir)
    chat_fnames_new = code_graph.find_files([repo_dir])

    tags, G = code_graph.get_code_graph(chat_fnames_new)

    print("---------------------------------")
    print(f"🏅 Successfully constructed the code graph for repo directory {repo_dir}")
    print(f"   Number of nodes: {len(G.nodes)}")
    print(f"   Number of edges: {len(G.edges)}")
    print("---------------------------------")

    # Save graph
    with open(graph_file, 'wb') as f:
        pickle.dump(G, f)
    
    # Save tags
    with open(tags_file, 'w') as f:
        for tag in tags:
            line = json.dumps({
                "fname": tag.fname,
                'rel_fname': tag.rel_fname,
                'line': tag.line,
                'name': tag.name,
                'kind': tag.kind,
                'category': tag.category,
                'info': tag.info,
            })
            f.write(line + '\n')
            
    print(f"🏅 Successfully cached code graph and node tags in directory '{output_dir}'")

if __name__ == "__main__":
    main()