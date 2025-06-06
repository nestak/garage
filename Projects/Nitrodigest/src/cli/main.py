from argparse import ArgumentParser
import os
import tempfile
import sys
import yaml
from datetime import datetime

from .summarizer import (
    OllamaSummarizer,
    ConfigurationError
)
from .config import Config


def main():
    parser = ArgumentParser(
        description="nitrodigest - TLDR text, privately",
        epilog="Visit docs, if you need more information: https://frodigo.com/projects/nitrodigest/docs, or report issues: https://github.com/frodigo/garage/issues if something doesn't work as expected."
    )
    parser.add_argument(
        "--input",
        help="Path to a single file or directory to summarize"
    )
    parser.add_argument(
        "--model",
        default="mistral",
        help="Model to use for summarization (default: mistral)"
    )
    parser.add_argument(
        "--ollama-api-url",
        default="http://localhost:11434",
        help="URL of the local Ollama API (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout in seconds for API requests to Ollama (default: 300)"
    )
    parser.add_argument(
        "--prompt-file",
        help="Path to custom prompt template file (overrides config)"
    )
    parser.add_argument(
        "--prompt",
        help="Direct prompt content (overrides both config and prompt-file)"
    )

    args = parser.parse_args()

    if args.input and not os.path.exists(args.input):
        print(f"Error: Input path '{args.input}' does not exist")
        return -1

    try:
        temp_prompt_file = None
        if args.prompt:
            temp = tempfile.NamedTemporaryFile(mode='w', delete=False)
            temp.write(args.prompt)
            temp.close()
            temp_prompt_file = temp.name

        config = Config(
            model=args.model,
            ollama_api_url=args.ollama_api_url,
            timeout=args.timeout,
            prompt_file=temp_prompt_file
        )

    except Exception as e:
        print(f"Configuration error: {e}")
        return -1

    try:
        summarizer = OllamaSummarizer(
            model=config.model,
            ollama_api_url=config.ollama_api_url,
            timeout=config.timeout,
            prompt_file=config.prompt_file
        )
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        return -1
    except Exception as e:
        print(f"Unexpected error initializing summarizer: {e}")
        return -1

    # Handle input file or directory
    if args.input:
        if os.path.isfile(args.input):
            process_file(args.input, summarizer)
        elif os.path.isdir(args.input):
            process_directory(args.input, summarizer)
        else:
            print(f"Error: '{args.input}' is neither a file nor a directory")
            return -1
    else:
        print("Error: No input file or directory specified. Use --input to specify a file or directory to summarize.")
        return -1

    # Clean up temporary prompt file if it was created
    if (args.prompt and config.prompt_file and
            os.path.exists(config.prompt_file)):
        os.remove(config.prompt_file)
        print("Cleaned up temporary prompt file.")


def process_file(file_path, summarizer):
    """Process a single file for summarization"""
    try:
        print(f"Processing file: {file_path}", file=sys.stderr)

        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            print(f"Warning: File '{file_path}' is empty", file=sys.stderr)
            return

        # Create metadata from file info
        file_name = os.path.basename(file_path)
        metadata = {
            'title': file_name,
            'source': 'file://' + os.path.abspath(file_path),
            'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S"),
            'id': file_path
        }

        # Generate summary
        print(f"Generating summary for {file_name}...", file=sys.stderr)
        result = summarizer.summarize(content, metadata)

        if not result.is_success():
            print(
                f"Failed to generate summary: {result.error}", file=sys.stderr)
            return -1

        summary = result.summary

        print('---')
        yaml.dump(
            {
                'title': metadata.get('title', 'Untitled'),
                'source': metadata.get('source', 'Unknown'),
                'date': metadata.get('date', datetime.now().strftime("%Y-%m-%d")),
                'id': metadata.get('id', ''),
                'summary_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'model': result.model_used,
                'tokens': result.tokens_used
            },
            sys.stdout,
            default_flow_style=False,
            allow_unicode=True
        )
        print('---\n')
        print(summary)

    except Exception as e:
        print(f"Error processing file '{file_path}': {e}", file=sys.stderr)


def process_directory(directory_path, summarizer):
    """Process all text files in a directory for summarization"""
    print(f"Processing directory: {directory_path}", file=sys.stderr)

    # Get all files in directory
    file_count = 0
    success_count = 0

    for root, _, files in os.walk(directory_path):
        for filename in files:
            # Only process text files - check common text file extensions
            if filename.lower().endswith(('.txt', '.md', '.html', '.htm', '.xml', '.json', '.csv', '.log')):
                file_path = os.path.join(root, filename)
                try:
                    process_file(file_path, summarizer)
                    success_count += 1
                except Exception as e:
                    print(f"Error processing '{file_path}': {e}")
                file_count += 1

    print(
        f"Directory processing complete: {success_count} of {file_count} files processed successfully", file=sys.stderr)


if __name__ == "__main__":
    main()
