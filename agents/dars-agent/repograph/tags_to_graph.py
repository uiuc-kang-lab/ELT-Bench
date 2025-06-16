import json
import glob
import pickle
import networkx as nx
from collections import namedtuple, defaultdict
import yaml
import os
from pathlib import Path
from tqdm import tqdm
import concurrent.futures

# Define the Tag namedtuple to match the structure in your JSON
Tag = namedtuple("Tag", "rel_fname fname line name kind category info")

def read_config(config_file='t2g_config.yaml'):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def read_tags_from_json(json_file):
    with open(json_file, 'r') as f:
        tag_list = json.load(f)
    return [Tag(**tag_dict) for tag_dict in tag_list]

def create_graph_from_tags(tags):
    G = nx.MultiDiGraph()
    
    # Pre-process tags
    class_tags = defaultdict(list)
    ref_tags = []
    def_tags = []
    
    for tag in tags:
        G.add_node(tag.name, category=tag.category, info=tag.info, fname=tag.fname, line=tag.line, kind=tag.kind)
        if tag.category == 'class':
            class_tags[tag.name].extend(tag.info.split('\n'))
        elif tag.kind == 'ref':
            ref_tags.append(tag)
        elif tag.kind == 'def':
            def_tags.append(tag)

    # Add edges for class functions
    for class_name, functions in class_tags.items():
        G.add_edges_from((class_name, f.strip()) for f in functions if f.strip())

    # Add edges for references
    def_names = set(tag.name for tag in def_tags)
    G.add_edges_from((tag.name, tag.name) for tag in ref_tags if tag.name in def_names)

    return G

def save_graph_as_pkl(graph, output_file):
    with open(output_file, 'wb') as f:
        pickle.dump(graph, f)

def process_json_file(json_file):
    # Keep the graph file in the same directory as the JSON file
    json_dir = os.path.dirname(json_file)
    
    # Read tags from the JSON file
    tags = read_tags_from_json(json_file)
    
    # Create graph from tags
    G = create_graph_from_tags(tags)
    
    # Save graph as PKL in the same directory as tags.json
    graph_file = os.path.join(json_dir, 'graph.pkl')
    save_graph_as_pkl(G, graph_file)
    
    return os.path.basename(json_file), len(G.nodes), len(G.edges)

if __name__ == "__main__":
    config = read_config()
    files = glob.glob(f"{config['tags_dir']}/*/tags*.json")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=config['max_workers']) as executor:
        future_to_file = {executor.submit(process_json_file, json_file): json_file for json_file in files}
        
        for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(files)):
            json_file = future_to_file[future]
            try:
                project, nodes, edges = future.result()
                print(f"Processed {project}")
                print(f"Number of nodes: {nodes}")
                print(f"Number of edges: {edges}")
                print()
            except Exception as exc:
                print(f'{json_file} generated an exception: {exc}')
