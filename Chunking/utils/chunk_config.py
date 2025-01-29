from functools import lru_cache
from typing import List

import git
import yaml


class ChunkConfig:
    """
    Configuration settings for chunking files.
    """

    exclude_dirs: list[str] = [
        # vcs / code editor folders
        ".git",
        ".vscode",
        # javascript / typescript
        "node_modules",
        "build",
        "dist",
        "package-lock.json",
        # common
        ".venv",
        "venv",
        "patch",
        "packages/blobs",
        # emailable-report-template.html should be part of repo config and should not be handled here, will be taken care of
        # in the future
        "emailable-report-template.html",
        # specific file handling for "tata1mg/thanos", will be taken care of in future
        ".docker",
        "config.ru",
        "Rakefile",
        "config/brakeman.ignore",
    ]
    exclude_exts: list[str] = [
        # vcs files to ignore
        ".gitignore",
        ".md",
        "LICENSE",
        ".sh",
        ".patch",
        ".patch.disabled",
        # images types
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".bmp",
        ".tiff",
        ".svg",
        ".webp",
        # audio / video types
        ".mp3",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wmv",
        ".3gp",
        ".3g2",
        ".wav",
        ".wma",
        ".ogg",
        ".flac",
        ".rm",
        ".swf",
        ".flv",
        ".iso",
        ".bin",
        ".aiff",
        # fonts types
        ".woff",
        ".woff2",
        ".eot",
        ".otf",
        ".m4a",
        ".m4v",
        ".ttf",
        # javascript / typescript
        ".min.js",
        ".min.js.map",
        ".npmrc",
        ".eslintignore",
        ".browserslistrc",
        ".eslintrc",
        # css / scss / less types
        ".min.css",
        ".min.css.map",
        ".css",
        ".scss",
        ".less",
        # python
        ".pyc",
        ".coverage",
        "pnpm-lock.yaml",
        ".lock",
        # ruby
        ".rspec",
        ".keep",
        ".ruby-version",
        # teraform
        ".tfstate",
        ".tfstate.backup",
        # java
        ".jar",
        # jupiter notebook extension
        ".ipynb",
        # extension for browser download file
        ".download",
        # compression types
        ".tar",
        ".zip",
        ".7z",
        ".gz",
        ".rar",
        # pdf files types
        ".pdf",
        ".pub",
        # word / doc types
        ".doc",
        ".docx",
        # sheet / excel type
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".parquet",
        # aws file type ( for security keys, etc )
        ".pem",
        # miscellaneous
        ".dfm",
        ".dfn",
        ".feature",
        "deputy_dev.yaml",
        # Below mentioned files and extensions are for "/tata1mg/app-automation-suite" repo, ideally we should give a functionality for the service
        # owner to configure at their repo level, but for the time being placing a comment over here for future development
        ".xml",
        "chromedriver",
        # Ideally, we should not be excluding .yml file from chunking, this is temporary for "tata1mg/thanos" ruby services and will be handled in future usecase
        ".yml",
        "Capfile",
        # Jade was used earlier for server side rendering, back when React/Angular was not there, we use in "tata1mg/HKPSpydoc",
        # but no active development has taken place over years, it's in maintainenece mode and can be excluded
        ".jade",
    ]
    max_single_dir_file_threshold: int = 240


# We are not currently using this function as of now, as this would require adding deputy_dev.yaml in the
# existing repo, which we are not considering as part of initial release, but later on should be considered
# to give more flexibility to the user to allow which files should be chunked.
@lru_cache(maxsize=None)
def get_blocked_dirs(repo: git.Repo) -> List[str]:
    """
    Get blocked directories from the repository's deputy_dev.yaml file.

    Args:
        repo (GitRepo): The Git repository.

    Returns:
        List[str]: A list of blocked directories.
    """
    try:
        yaml_content = repo.get_contents("deputy_dev.yaml").decoded_content.decode("utf-8")
        deputy_dev_yaml = yaml.safe_load(yaml_content)
        dirs = deputy_dev_yaml.get("blocked_dirs", [])
        return dirs
    except SystemExit:
        raise SystemExit
    except Exception:
        return []
