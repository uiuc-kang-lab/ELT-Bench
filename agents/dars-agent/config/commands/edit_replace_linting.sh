# @yaml
# signature: edit <to_replace> <new_content>
# docstring: Replaces occurrences of <to_replace> with <new_content> in the currently open file.
# arguments:
#   to_replace:
#       type: string
#       description: The text to be replaced in the file.
#       required: true
#   new_content:
#       type: string
#       description: The new text to replace with.
#       required: true
edit() {
    # Check if a file is open
    if [ -z "$CURRENT_FILE" ]; then
        echo 'No file open. Use the `open` command first.'
        return
    fi

    # Read arguments via positional parameters
    local to_replace="$1"
    shift
    local new_content="$@"

    # Validate arguments
    if [[ -z "$to_replace" ]]; then
        echo "Error: 'to_replace' must not be empty."
        return
    fi

    if [[ "$to_replace" == "$new_content" ]]; then
        echo "Error: 'to_replace' and 'new_content' must be different."
        return
    fi

    # Write 'to_replace' and 'new_content' to temporary files to handle multi-line inputs
    local to_replace_file=$(mktemp)
    local new_content_file=$(mktemp)
    printf '%b\n' "$to_replace" > "$to_replace_file"
    printf '%b\n' "$new_content" > "$new_content_file"

    # Set up a trap to remove temporary files on exit
    trap 'rm -f "$to_replace_file" "$new_content_file"' EXIT

    # Call the Python wrapper script
    export ENABLE_AUTO_LINT="true"
    AIDER_ENV="aider"
    CONDA_BASE=$(conda info --base)
    AIDER_PYTHON_EXEC="$CONDA_BASE/envs/$AIDER_ENV/bin/python"
    $AIDER_PYTHON_EXEC /root/commands/_edit_replace "$CURRENT_FILE" "$to_replace_file" "$new_content_file"

    # Remove the trap since we've already removed the files
    trap - EXIT
}

# @yaml
# signature: insert <line_number> <content>
# docstring: Inserts <content> at the given <line_number> in the currently open file.
# arguments:
#   line_number:
#       type: int
#       description: The line number where the content should be inserted.
#       required: true
#   content:
#       type: string
#       description: The content to insert at the specified line number.
#       required: true
insert() {
    # Check if a file is open
    if [ -z "$CURRENT_FILE" ]; then
        echo 'No file open. Use the `open` command first.'
        return
    fi

    # Read arguments via positional parameters
    local line_number="$1"
    shift
    local content="$@"

    # Validate arguments
    if [[ -z "$line_number" || ! "$line_number" =~ ^[0-9]+$ ]]; then
        echo "Error: 'line_number' must be a valid integer."
        return
    fi

    if [[ -z "$content" ]]; then
        echo "Error: 'content' must not be empty."
        return
    fi

    # Write 'content' to a temporary file to handle multi-line inputs
    local content_file=$(mktemp)
    printf '%b\n' "$content" > "$content_file"

    # Set up a trap to remove temporary files on exit
    trap 'rm -f "$content_file"' EXIT

    # Call the Python wrapper script
    export ENABLE_AUTO_LINT="true"
    AIDER_ENV="aider"
    CONDA_BASE=$(conda info --base)
    AIDER_PYTHON_EXEC="$CONDA_BASE/envs/$AIDER_ENV/bin/python"
    $AIDER_PYTHON_EXEC /root/commands/_insert_content "$CURRENT_FILE" "$line_number" "$content_file"

    # Remove the trap since we've already removed the files
    trap - EXIT
}

# @yaml
# signature: append <content>
# docstring: Appends <content> to the end of the currently open file.
# arguments:
#   content:
#       type: string
#       description: The content to append to the end of the file.
#       required: true
append() {
    # Check if a file is open
    if [ -z "$CURRENT_FILE" ]; then
        echo 'No file open. Use the `open` command first.'
        return
    fi

    # Read argument via positional parameter
    local content="$@"

    # Validate argument
    if [[ -z "$content" ]]; then
        echo "Error: 'content' must not be empty."
        return
    fi

    # Write 'content' to a temporary file to handle multi-line inputs
    local content_file=$(mktemp)
    printf '%b\n' "$content" > "$content_file"

    # Set up a trap to remove temporary files on exit
    trap 'rm -f "$content_file"' EXIT

    # Call the Python wrapper script
    export ENABLE_AUTO_LINT="true"
    AIDER_ENV="aider"
    CONDA_BASE=$(conda info --base)
    AIDER_PYTHON_EXEC="$CONDA_BASE/envs/$AIDER_ENV/bin/python"
    $AIDER_PYTHON_EXEC /root/commands/_append_file "$CURRENT_FILE" "$content_file"

    # Remove the trap since we've already removed the files
    trap - EXIT
}