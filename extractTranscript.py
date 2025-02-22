import os
import re
import argparse
import xml.etree.ElementTree as ET
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def format_timestamp(seconds):
    """Format seconds into HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"


def extract_transcript(ttml_content, output_path, include_timestamps=False):
    """Extract transcript from TTML content and save it to a text file."""
    try:
        root = ET.fromstring(ttml_content)
        transcript = []

        # Find all <p> elements the TTML file
        paragraphs = root.findall(".//{http://www.w3.org/ns/ttml}p")

        for paragraph in paragraphs:
            paragraph_text = ""
            for span in paragraph.findall(".//{http://www.w3.org/ns/ttml}span"):
                if span.text:
                    paragraph_text += span.text.strip() + " "

            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                if include_timestamps and "begin" in paragraph.attrib:
                    timestamp = format_timestamp(float(paragraph.attrib["begin"].replace("s", "")))
                    transcript.append(f"[{timestamp}] {paragraph_text}")
                else:
                    transcript.append(paragraph_text)

        # Save the transcript to a file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(transcript))
        print(f"Transcript saved to {output_path}")

    except ET.ParseError as e:
        print(f"Error parsing TTML file: {e}")


def find_ttml_files(directory):
    """Recursively find all TTML files in a directory."""
    ttml_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".ttml"):
                match = re.search(r"PodcastContent([^/]+)", os.path.join(root, file))
                if match:
                    ttml_files.append({
                        "path": os.path.join(root, file),
                        "id": match.group(1)
                    })
    return ttml_files



def summarize_transcript(transcript):
    response = client.chat.completions.create(model="gpt-4",  # Use "gpt-4" if you have access
    messages=[
        {"role": "system", "content": "You are a helpful assistant that summarizes podcast transcripts."},
        {"role": "user", "content": f"Summarize the following podcast transcript in bullet points:\n\n{transcript}"}
    ],
    max_tokens=200)
    return response.choices[0].message.content.strip()


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Extract transcripts from TTML files.")
    parser.add_argument("--timestamps", action="store_true", help="Include timestamps in the transcript.")
    parser.add_argument("--input", type=str, help="Path to a single TTML file.")
    parser.add_argument("--output", type=str, help="Path to save the transcript for a single file.")
    args = parser.parse_args()

    # Base directory for TTML files
    ttml_base_dir = os.path.expanduser("~/Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML")
    output_dir = "./transcripts"

    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if args.input and args.output:
        # Single file mode
        with open(args.input, "r", encoding="utf-8") as f:
            ttml_content = f.read()
        extract_transcript(ttml_content, args.output, args.timestamps)
    else:
        # Batch mode
        print("Searching for TTML files...")
        ttml_files = find_ttml_files(ttml_base_dir)
        print(f"Found {len(ttml_files)} TTML files")

        # Create a map to track filename occurrences
        filename_counts = {}

        for file in ttml_files:
            base_filename = file["id"]
            count = filename_counts.get(base_filename, 0)
            suffix = f"-{count}" if count > 0 else ""
            output_path = os.path.join(output_dir, f"{base_filename}{suffix}.txt")

            # Increment the count for this filename
            filename_counts[base_filename] = count + 1

            with open(file["path"], "r", encoding="utf-8") as f:
                ttml_content = f.read()
            extract_transcript(ttml_content, output_path, args.timestamps)

        transcript = open(output_path, "r", encoding="utf-8").read()
        summary = summarize_transcript(transcript)
        summary_path = os.path.join(output_dir, f"{base_filename}{suffix}_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()