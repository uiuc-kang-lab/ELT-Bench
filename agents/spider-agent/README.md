# Spider-Agent
Spider-Agent is proposed by [xlang-ai](https://github.com/xlang-ai/Spider2) which primarily focused on database-related coding tasks and projects. We have modified it for ELT-Bench to evaluate its performance.

## Evaluating Spider-Agent on ELT-Bench
### Setup
```
conda create -n spider2 python=3.11
conda activate spider2
pip install -r requirements.txt
export OPENAI_API_KEY=your_openai_api_key
export ANTHROPIC_API_KEY=your_anthropic_api_key
export FIREWORKS_API_KEY=your_fireworks_api_key
```
### Running experiments
```
python run.py --suffix eltbench --model model_name
```

Model options: ['gpt-4o', 'accounts/fireworks/models/llama-v3p1-405b-instruct', 'accounts/fireworks/models/qwen2p5-coder-32b-instruct', 'accounts/fireworks/models/deepseek-r1', 'claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022']
## 🚀 Quickstart

### Setup

#### 1. Conda Env
```
# Clone the Spider 2.0 repository

# Optional: Create a Conda environment for Spider 2.0
# conda create -n spider2 python=3.11
# conda activate spider2

# Install required dependencies
pip install -r requirements.txt
```

#### 2. Run Spider-Agent

##### Set LLM API Key

```
export AZURE_API_KEY=your_azure_api_key
export AZURE_ENDPOINT=your_azure_endpoint
export OPENAI_API_KEY=your_openai_api_key
export GEMINI_API_KEY=your_genmini_api_key
```

##### Run 


```python
python run.py --suffix <The name of this experiment>
python run.py --model gpt-4o --suffix test1
```


## Agent Framework

#### Action

- `Bash`: Executes shell commands, such as checking file information, running code, or executing DBT commands.
- `CREATE_FILE`: Creates a new file with specified content.
- `EDIT_FILE`: Edits or overwrites the content of an existing file.
- `BIGQUERY_EXEC_SQL`: Executes a SQL query on BigQuery, with an option to save the results.
- `BQ_GET_TABLES`: Retrieves all table names and schemas from a specified BigQuery dataset.
- `BQ_GET_TABLE_INFO`: Retrieves detailed column information for a specific table in BigQuery.
- `BQ_SAMPLE_ROWS`: Samples a specified number of rows from a BigQuery table and saves them as JSON.
- `Terminate`: Marks the completion of the task, returning the final result or file path.



