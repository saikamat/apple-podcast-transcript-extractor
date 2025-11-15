#!/usr/bin/env python3
import xml.etree.ElementTree as ET

def extract_transcript(ttml_content, include_timestamps=False):
    """Extract transcript from TTML content."""
    try:
        root = ET.fromstring(ttml_content)
        transcript = []

        # Find all <p> elements in the TTML file
        paragraphs = root.findall(".//{http://www.w3.org/ns/ttml}p")

        for paragraph in paragraphs:
            paragraph_text = ""
            for span in paragraph.findall(".//{http://www.w3.org/ns/ttml}span"):
                if span.text:
                    paragraph_text += span.text.strip() + " "

            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                if include_timestamps and "begin" in paragraph.attrib:
                    # Simple timestamp formatting
                    timestamp = paragraph.attrib["begin"]
                    transcript.append(f"[{timestamp}] {paragraph_text}")
                else:
                    transcript.append(paragraph_text)

        return "\n\n".join(transcript)

    except ET.ParseError as e:
        return f"Error parsing TTML file: {e}"

# Read your TTML file
with open('/Users/saikamat/Documents/Python Scripts/apple-podcast-transcript-extractor/uploads/transcript_1000733635375.ttml-1000733635375.ttml', 'r', encoding='utf-8') as f:
    ttml_content = f.read()

# Extract clean transcript
clean_transcript = extract_transcript(ttml_content, include_timestamps=False)

# Save the clean transcript
with open('/Users/saikamat/Documents/Python Scripts/apple-podcast-transcript-extractor/clean_transcript.txt', 'w', encoding='utf-8') as f:
    f.write(clean_transcript)

print("Clean transcript saved to clean_transcript.txt")