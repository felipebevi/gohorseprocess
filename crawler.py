import os
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

class StaticSiteDownloader:
    def __init__(self, root_url, output_dir=None):
        self.root_url = root_url.rstrip("/")
        self.output_dir = Path(output_dir or urlparse(root_url).netloc)
        self.visited = set()
        self.queue = [self.root_url]

    def run_curl(self, url, output_file):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        header_args = []
        for key, value in headers.items():
            header_args.extend(["-H", f"{key}: {value}"])
        curl_command = ["curl", "-L", "-o", output_file] + header_args + [url]
        try:
            subprocess.run(curl_command, check=True)
            print(f"Downloaded: {url} -> {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to download {url}: {e}")

    def save_html(self, url, content):
        parsed_url = urlparse(url)
        path = parsed_url.path.lstrip("/") or "index.html"
        file_path = self.output_dir / path
        if not file_path.suffix:
            file_path = file_path.with_suffix(".html")
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)

        print(f"Saved: {file_path}")

    def process_html(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["a", "link", "script", "img"]):
            attr = "href" if tag.name != "img" else "src"
            if tag.has_attr(attr):
                original_url = tag[attr]
                full_url = urljoin(base_url, original_url)
                parsed_url = urlparse(full_url)
                if parsed_url.netloc != urlparse(self.root_url).netloc:
                    continue  # Skip external links

                # Ensure local path is unique and valid
                local_path = self.output_dir / parsed_url.path.lstrip("/")
                if not local_path.suffix:
                    local_path = local_path.with_suffix(".html")
                if local_path.exists() and not local_path.is_dir():
                    local_path.unlink()  # Remove file if it conflicts with a directory
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self.run_curl(full_url, str(local_path))

                # Adjust the tag to point to the local file
                tag[attr] = os.path.relpath(local_path, self.output_dir)

        return soup.prettify()

    def crawl(self):
        if self.output_dir.exists():
            if self.output_dir.is_dir():
                print(f"Clearing existing output directory: {self.output_dir}")
                for item in self.output_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        for subitem in item.iterdir():
                            if subitem.is_file():
                                subitem.unlink()
                            elif subitem.is_dir():
                                os.rmdir(subitem)
                        os.rmdir(item)
            else:
                print(f"Removing conflicting file: {self.output_dir}")
                self.output_dir.unlink()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        while self.queue:
            current_url = self.queue.pop(0)
            if current_url in self.visited:
                continue

            print(f"Crawling: {current_url}")
            local_html_path = self.output_dir / urlparse(current_url).path.lstrip("/")
            if local_html_path.is_dir():
                local_html_path /= "index.html"
            elif not local_html_path.suffix:
                local_html_path = local_html_path.with_suffix(".html")
            local_html_path.parent.mkdir(parents=True, exist_ok=True)

            self.run_curl(current_url, str(local_html_path))

            try:
                with open(local_html_path, "r", encoding="utf-8") as f:
                    html = f.read()
            except FileNotFoundError:
                print(f"Failed to read downloaded HTML: {current_url}")
                continue

            processed_html = self.process_html(html, current_url)
            with open(local_html_path, "w", encoding="utf-8") as f:
                f.write(processed_html)

            self.visited.add(current_url)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download a website and convert it into a static offline version.")
    parser.add_argument("url", help="The root URL of the website to download.")
    parser.add_argument("--output", help="The output directory for the offline website.")
    args = parser.parse_args()

    downloader = StaticSiteDownloader(args.url, args.output)
    downloader.crawl()
