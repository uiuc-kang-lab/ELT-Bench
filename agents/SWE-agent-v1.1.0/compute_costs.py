import os
import json
import csv
import argparse
from pathlib import Path

# Cost configuration (in dollars per 1 million tokens)
INPUT_COST_PER_1M_TOKENS = 2.28
OUTPUT_COST_PER_1M_TOKENS = 11.40

def get_databases():
    """Get list of database names from tasks directory."""
    tasks_path = Path('../../tasks')
    if not tasks_path.exists():
        print(f"Warning: {tasks_path} does not exist")
        return []

    databases = [f.name for f in tasks_path.iterdir() if f.is_dir()]
    databases.sort()
    return databases

def calculate_costs(tokens_sent, tokens_received):
    """
    Calculate input and output costs.
    Uses global cost configuration variables.
    """
    input_cost = (tokens_sent / 1_000_000) * INPUT_COST_PER_1M_TOKENS
    output_cost = (tokens_received / 1_000_000) * OUTPUT_COST_PER_1M_TOKENS
    return input_cost, output_cost

def process_trajectory_file(traj_file_path):
    """Extract model_stats from a trajectory file."""
    try:
        with open(traj_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Navigate to model_stats
        if 'info' in data and 'model_stats' in data['info']:
            model_stats = data['info']['model_stats']
            return {
                'tokens_sent': model_stats.get('tokens_sent', 0),
                'tokens_received': model_stats.get('tokens_received', 0),
                'api_calls': model_stats.get('api_calls', 0)
            }
        else:
            print(f"Warning: model_stats not found in {traj_file_path}")
            return None
    except FileNotFoundError:
        print(f"Warning: File not found - {traj_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Warning: JSON decode error in {traj_file_path}: {e}")
        return None
    except Exception as e:
        print(f"Warning: Error processing {traj_file_path}: {e}")
        return None

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Process trajectory files and generate cost analysis CSV.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Example usage:
  python script.py swe-agent_claude4.5_function-calling.csv
  python script.py my_analysis.csv

Current cost configuration:
  Input cost:  ${INPUT_COST_PER_1M_TOKENS} per 1M tokens
  Output cost: ${OUTPUT_COST_PER_1M_TOKENS} per 1M tokens
        """
    )
    parser.add_argument(
        'output_filename',
        help='Name of the output CSV file (will be saved in costs/ directory)'
    )
    
    args = parser.parse_args()
    output_filename = args.output_filename
    
    # Ensure .csv extension
    if not output_filename.endswith('.csv'):
        output_filename += '.csv'
    
    # Get database names
    databases = get_databases()
    
    if not databases:
        print("No databases found. Please check the ../tasks directory exists.")
        return
    
    print(f"Found {len(databases)} databases: {databases}")
    
    # Base trajectory directory
    traj_base_dir = Path('trajectories/chz')
    
    if not traj_base_dir.exists():
        print(f"Error: {traj_base_dir} does not exist")
        return
    
    # Prepare data for CSV
    results = []
    
    # Process each database
    for db_name in databases:
        folder_name = f"no_config__openai--aws--claude-sonnet-4-5__t-0.00__p-None__c-0.00___{db_name}/{db_name}"
        traj_file = traj_base_dir / folder_name / f"{db_name}.traj"
        
        print(f"\nProcessing: {db_name}")
        print(f"  Looking for: {traj_file}")
        
        if not traj_file.exists():
            print(f"  Warning: Trajectory file not found")
            continue
        
        # Extract model stats
        stats = process_trajectory_file(traj_file)
        
        if stats:
            tokens_sent = stats['tokens_sent']
            tokens_received = stats['tokens_received']
            api_calls = stats['api_calls']
            
            # Calculate costs
            input_cost, output_cost = calculate_costs(tokens_sent, tokens_received)
            
            total_cost = input_cost + output_cost
            
            results.append({
                'db_name': db_name,
                'tokens_sent': tokens_sent,
                'tokens_received': tokens_received,
                'input_cost': round(input_cost, 6),
                'output_cost': round(output_cost, 6),
                'total_cost': round(total_cost, 6),
                'api_calls': api_calls
            })
            
            print(f"  ✓ Tokens sent: {tokens_sent:,}")
            print(f"  ✓ Tokens received: {tokens_received:,}")
            print(f"  ✓ API calls: {api_calls}")
            print(f"  ✓ Input cost: ${input_cost:.6f}")
            print(f"  ✓ Output cost: ${output_cost:.6f}")
            print(f"  ✓ Total cost: ${(input_cost + output_cost):.6f}")
    
    # Create costs directory if it doesn't exist
    costs_dir = Path('costs')
    costs_dir.mkdir(exist_ok=True)
    
    # Write to CSV
    output_file = costs_dir / output_filename
    
    if results:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['db_name', 'tokens_sent', 'tokens_received', 'input_cost', 'output_cost', 'total_cost', 'api_calls']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n{'='*60}")
        print(f"SUCCESS: CSV file created at {output_file}")
        print(f"Total databases processed: {len(results)}")
        
        # Calculate totals
        total_tokens_sent = sum(r['tokens_sent'] for r in results)
        total_tokens_received = sum(r['tokens_received'] for r in results)
        total_input_cost = sum(r['input_cost'] for r in results)
        total_output_cost = sum(r['output_cost'] for r in results)
        total_cost = sum(r['total_cost'] for r in results)
        total_api_calls = sum(r['api_calls'] for r in results)
        
        print(f"\nTOTALS:")
        print(f"  Total tokens sent: {total_tokens_sent:,}")
        print(f"  Total tokens received: {total_tokens_received:,}")
        print(f"  Total input cost: ${total_input_cost:.6f}")
        print(f"  Total output cost: ${total_output_cost:.6f}")
        print(f"  Total cost: ${total_cost:.6f}")
        print(f"  Total API calls: {total_api_calls}")
        print(f"{'='*60}")
        
        # Write totals to separate CSV
        totals_filename = output_filename.replace('.csv', '_totals.csv')
        totals_file = costs_dir / totals_filename
        
        with open(totals_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['metric', 'value']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerow({'metric': 'total_tokens_sent', 'value': total_tokens_sent})
            writer.writerow({'metric': 'total_tokens_received', 'value': total_tokens_received})
            writer.writerow({'metric': 'total_input_cost', 'value': round(total_input_cost, 6)})
            writer.writerow({'metric': 'total_output_cost', 'value': round(total_output_cost, 6)})
            writer.writerow({'metric': 'total_cost', 'value': round(total_cost, 6)})
            writer.writerow({'metric': 'total_api_calls', 'value': total_api_calls})
            writer.writerow({'metric': 'databases_processed', 'value': len(results)})
        
        print(f"\nTotals CSV created at {totals_file}")
        print(f"{'='*60}")
    else:
        print("\nNo results to write. Please check the file paths and database names.")

if __name__ == "__main__":
    main()