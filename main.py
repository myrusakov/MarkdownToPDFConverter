from datetime import datetime
import os
import markdown2
import pdfkit
import re
import subprocess


repo_path = r"D:\Books"  # Specify the path to the directory with md files
output_pdf_path = r"Books.pdf"  # Specify the path for the output file
excluded_files = ["README.md", "SUMMARY.md"]  # Specify the files to exclude from import
debug_html = False  # Is an output HTML file needed for debugging?
include_page_break = True  # Set to True to include a page break after each md file
enable_html_processing = True  # Set to False if no HTML modifications are required
filter_created_after = datetime(2025, 1, 1)  # Include only files created after this date (set to None to disable)
filter_created_before = datetime.now()  # Include only files created before this date (set to None to disable)

# Settings for wkhtmltopdf
options = {
    'enable-local-file-access': None,
    'encoding': "UTF-8",
    'footer-right': '[page]',
    'footer-font-size': '10',
    'image-quality': '100',
}

def gather_md_files(directory):
    md_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(".md"):
                continue
            if file in excluded_files:
                continue

            full_path = os.path.join(root, file)
            creation_time = get_creation_time(full_path)
            if filter_created_after and creation_time < filter_created_after:
                continue
            if filter_created_before and creation_time > filter_created_before:
                continue

            md_files.append(full_path)

    return md_files


def get_creation_time(filepath):
    # 1) Try to get the file creation time from Git (first commit date)
    try:
        relative_path = os.path.relpath(filepath, repo_path)
        timestamp = subprocess.check_output(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%ct", "--", relative_path],
            cwd=repo_path,
            stderr=subprocess.DEVNULL
        ).strip()

        if timestamp:
            return datetime.fromtimestamp(int(timestamp))

    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, OSError):
        # Git failed — fall back to OS timestamps
        pass

    # 2) OS fallback: try to get the file creation time (ctime)
    try:
        created_time = os.path.getctime(filepath)
        return datetime.fromtimestamp(created_time)
    except (OSError, ValueError):
        pass

    # 3) Final fallback: try modification time
    try:
        modified_time = os.path.getmtime(filepath)
        return datetime.fromtimestamp(modified_time)
    except (OSError, ValueError):
        return None


def remove_metadata(md_content):
    # Remove the metadata block if it is present
    return re.sub(r'^---.*?---\s+', '', md_content, flags=re.DOTALL)

def md_to_html(md_content):
    return markdown2.markdown(md_content, extras=["fenced-code-blocks", "tables"])

def convert_image_paths_to_absolute(html_content, base_path):
    def repl(match):
        rel = match.group(1)
        abs_path = os.path.abspath(os.path.join(str(base_path), rel))
        abs_path = abs_path.replace("\\", "/")  # Windows fix
        return f'<img src="file:///{abs_path}"'

    return re.sub(r'<img src="(.*?)"', repl, html_content)


def process_html(html_content):
    # Here you can perform any necessary processing on the HTML code
    # The code inside this function can be removed as it is tailored for a specific HTML structure,
    # and is used for more accurate page breaking

    # Wrap the found blocks in <section class="break">...</section>
    pattern = re.compile(r'(<h1>.*?</h1>\s*<h2>.*?</h2>.*?(?=<h2>|$))|(<h2>.*?</h2>.*?(?=<h2>|$))', re.DOTALL)
    html_content = re.sub(pattern, lambda match: f'<section class="break">{match.group(0).strip()}</section>',
                          html_content)

    # Regular expression to find <section class="break"> blocks
    pattern = re.compile(r'<section class="break">(.*?)</section>', re.DOTALL)

    # Function to replace the section if there is no <figure> inside
    def replace_section(match):
        section_content = match.group(1)
        if '<figure>' not in section_content and '<h1>' not in section_content:
            return section_content.strip()  # Return the content without <section>
        return match.group(0)  # Return the original <section> block if there is a <figure>

    # Replace sections in the HTML content
    html_content = re.sub(pattern, replace_section, html_content)
    return html_content

def combine_md_files_to_html(md_files):
    with open('style.css', 'r', encoding='utf-8') as css_file:
        styles = css_file.read()

    combined_html = f"<html><head><meta charset=\"UTF-8\"><style>{styles}</style></head><body>"

    for file_path in md_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            md_content = remove_metadata(md_content)
            html_content = md_to_html(md_content)
            html_content = convert_image_paths_to_absolute(html_content, os.path.dirname(file_path))

            if enable_html_processing:
                html_content = process_html(html_content)

            combined_html += f"<div>{html_content}</div>"
            if include_page_break:
                combined_html += "<div class=\"page-break\"></div>"

    combined_html += "</body></html>"

    return combined_html

def main():
    md_files = gather_md_files(repo_path)
    combined_html = combine_md_files_to_html(md_files)

    if debug_html:
        debug_html_path = "debug.html"
        with open(debug_html_path, 'w', encoding='utf-8') as debug_html_file:
            debug_html_file.write(combined_html)

    pdfkit.from_string(combined_html, output_pdf_path, options=options)
    print(f"PDF successfully saved at {output_pdf_path}")

if __name__ == "__main__":
    main()
