import os
import json
import glob
import yaml
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

def read_config(config_file='tags_update_config.yaml'):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def process_tag_file(tag_file):
    """
    Load tag file, update fname field and save back in original format.
    Returns bool indicating success/failure.
    """
    try:
        # Load and detect format
        with open(tag_file, 'r', encoding='utf-8') as f:
            content = f.read()
            try:
                tags = json.loads(content)
                is_indented = content.startswith('[\n  ')
                is_jsonl = False
            except json.JSONDecodeError:
                # Try JSONL format
                tags = [json.loads(line) for line in content.splitlines() if line.strip()]
                is_indented = False
                is_jsonl = True

        if not tags:
            print(f"Empty file: {tag_file}")
            return False

        repo_name = os.path.join('/', tag_file.split('/')[-2].split('-')[0])
        for tag in tags:
            tag['fname'] = os.path.join(repo_name, tag.get('rel_fname', ''))

        # Save with original format
        temp_file = tag_file + '.tmp'
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                if is_jsonl:
                    for tag in tags:
                        f.write(json.dumps(tag) + '\n')
                else:
                    json.dump(tags, f, indent=2 if is_indented else None)
            
            os.rename(temp_file, tag_file)
            return True

        except Exception as e:
            print(f"Error saving {tag_file}: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    except Exception as e:
        print(f"Error processing {tag_file}: {e}")
        return False

def main():
    config = read_config()
    tag_files = glob.glob(f"{config['tags_dir']}/*/tags*.json")

    with ThreadPoolExecutor(max_workers=config['max_workers']) as executor:
        results = list(tqdm(executor.map(process_tag_file, tag_files), 
                            total=len(tag_files),
                            desc="Processing tag files"))

    success_count = sum(results)
    print(f"Successfully processed {success_count} out of {len(tag_files)} files")

if __name__ == "__main__":
   main()