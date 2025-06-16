import pickle
import sys
import json
import argparse
import logging
from typing import Dict, List, Optional
from pathlib import Path
import networkx as nx
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class FunctionInfo:
    """Data class to store function information"""
    fname: str
    line: int
    name: str
    kind: str
    category: str
    info: dict

class CodeGraphRetriever:
    def __init__(self, graph_dir: str):
        """Initialize the code graph retriever with the directory containing graph files"""
        self.graph_dir = Path(graph_dir)
        self.graph: Optional[nx.DiGraph] = None
        self.tags: Dict = {}
        self.tags2names: Dict = {}
        
    def validate_paths(self) -> bool:
        """Validate that required files exist"""
        graph_path = self.graph_dir / 'graph.pkl'
        tags_path = self.graph_dir / 'tags.json'
        
        if not graph_path.exists():
            logger.error(f"Graph file not found: {graph_path}")
            return False
        if not tags_path.exists():
            logger.error(f"Tags file not found: {tags_path}")
            return False
        return True

    def load_graph(self) -> bool:
        """Load the graph from pickle file"""
        try:
            graph_path = self.graph_dir / 'graph.pkl'
            with open(graph_path, 'rb') as f:
                self.graph = pickle.load(f)
            return True
        except Exception as e:
            logger.error(f"Failed to load graph: {str(e)}")
            return False

    def load_tags(self) -> bool:
        """Load tags from JSON file with fallback to line-by-line reading"""
        tags_path = self.graph_dir / 'tags.json'
        
        # First attempt: Load as single JSON
        try:
            with open(tags_path, 'r', encoding='utf-8') as f:
                self.tags = json.load(f)
            self.tags2names = {tag['name']: tag for tag in self.tags}
            return True
        except json.JSONDecodeError:
            pass
            
        # Second attempt: Load line by line
        try:
            with open(tags_path, 'r', encoding='utf-8') as f:
                tags_lines = f.readlines()
            self.tags = [json.loads(tag) for tag in tags_lines if tag.strip()]
            self.tags2names = {tag['name']: tag for tag in self.tags}
            return True
        except Exception as e:
            return False

    def get_related_functions(self, func_name: str) -> List[FunctionInfo]:
        """Get related functions for the given function name"""
        if not self.graph or func_name not in self.graph:
            print(f"Function {func_name} not found in the repository")
            return []

        try:
            # Get predecessors and successors
            successors = list(self.graph.successors(func_name))
            predecessors = list(self.graph.predecessors(func_name))
            # Handle tab-separated strings if present
            all_related = []
            for item in successors + [func_name] + predecessors:
                if '\t' in item:
                    all_related.extend(item.split('\t'))
                else:
                    all_related.append(item)
            # Filter and convert to FunctionInfo objects
            returned_files = []
            for item in all_related:
                if item not in self.tags2names:
                    continue
                    
                tag_info = self.tags2names[item]
                
                # Skip test files
                if 'test' in tag_info['fname'].lower():
                    continue
                
                func_info = FunctionInfo(
                    fname=tag_info['fname'],
                    line=tag_info['line'],
                    name=tag_info['name'],
                    kind=tag_info['kind'],
                    category=tag_info['category'],
                    info=tag_info['info']
                )
                returned_files.append(func_info)
            
            return returned_files

        except Exception as e:
            logger.error(f"Error processing function {func_name}: {str(e)}")
            return []

def main():
    parser = argparse.ArgumentParser(description="Retrieve related functions from a code graph")
    parser.add_argument("--search_term", required=True, help="Name of the function to search for")
    parser.add_argument("--codegraph_dir", default="./", help="Directory containing graph.pkl and tags.json")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Initialize retriever
    retriever = CodeGraphRetriever(args.codegraph_dir)
    
    # Validate and load data
    if not retriever.validate_paths():
        sys.exit(1)
    
    if not retriever.load_graph():
        sys.exit(1)
        
    if not retriever.load_tags():
        sys.exit(1)
    
    # Get and print results
    results = retriever.get_related_functions(args.search_term)
    if results:
        for result in results:
            if len(str(result.info)) > 1000:
                result.info = str(result.info)[:1000] + "... (truncated)"
        results = results[:5]
        print(json.dumps([vars(r) for r in results], indent=2))
    else:
        print("No related functions found")
        sys.exit(1)

if __name__ == '__main__':
    main()