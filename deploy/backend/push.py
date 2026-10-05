"""Create (or update) the Hugging Face Space and its private corpus dataset, set the secrets, and upload.

Run from the repository root with huggingface_hub installed:
    python deploy/backend/push.py <staged-dir> <dump-file> <web-origins> [space-name]
<web-origins> is the full comma list for CORS_ORIGINS. Reads HF_TOKEN, OPENAI_API_KEY and ADMIN_TOKEN from .env.
Prints no secret values. The dump (fatwa texts) goes to a private dataset; the public Space only reads it at start.
"""

import secrets
import sys
from pathlib import Path

from huggingface_hub import HfApi


def read_env(path: str) -> dict[str, str]:
    env = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            env[key.strip()] = value.strip().strip("'\"")
    return env


folder, dump, origins = sys.argv[1], sys.argv[2], sys.argv[3]
name = sys.argv[4] if len(sys.argv) > 4 else "tibyan"
env = read_env(".env")
api = HfApi(token=env["HF_TOKEN"])
owner = api.whoami()["name"]
repo, corpus = f"{owner}/{name}", f"{owner}/{name}-corpus"

api.create_repo(corpus, repo_type="dataset", private=True, exist_ok=True)
api.upload_file(path_or_fileobj=dump, path_in_repo="tibyan.dump", repo_id=corpus, repo_type="dataset")

api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
for key, value in {
    "OPENAI_API_KEY": env["OPENAI_API_KEY"],
    "ADMIN_TOKEN": env["ADMIN_TOKEN"],
    "CORPUS_TOKEN": env["HF_TOKEN"],
    "INTERNAL_API_TOKEN": secrets.token_urlsafe(32),
    "IP_HASH_SALT": secrets.token_urlsafe(16),
}.items():
    api.add_space_secret(repo, key, value)
api.add_space_variable(repo, "CORS_ORIGINS", origins)
api.add_space_variable(repo, "CORPUS_REPO", corpus)
api.upload_folder(
    repo_id=repo, repo_type="space", folder_path=folder, delete_patterns=["tibyan.dump", "data/corpus/*/*"],
    commit_message="Deploy Tibyan backend",
)
# Earlier versions shipped the dump in the Space; squashing removes it from the public history.
api.super_squash_history(repo_id=repo, repo_type="space", commit_message="Tibyan backend")
host = repo.replace("/", "-").replace("_", "-").replace(".", "-").lower()
print("space:", repo, f"url: https://{host}.hf.space", "| private corpus:", corpus)
