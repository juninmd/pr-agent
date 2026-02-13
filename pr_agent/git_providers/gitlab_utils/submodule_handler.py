import base64
import configparser
import re
import urllib.parse
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings

class GitLabSubmoduleHandler:
    def __init__(self, provider):
        self.provider = provider
        self._submodule_cache = {}

    def _get_gitmodules_map(self) -> dict[str, str]:
        try:
            proj = self.provider.gl.projects.get(self.provider.id_project)
        except Exception:
            return {}

        def _read_text(ref: str | None) -> str | None:
            if not ref:
                return None
            try:
                f = proj.files.get(file_path=".gitmodules", ref=ref)
            except Exception:
                return None

            try:
                raw = f.decode()
                if isinstance(raw, (bytes, bytearray)):
                    return raw.decode("utf-8", "ignore")
                if isinstance(raw, str):
                    return raw
            except Exception:
                pass

            try:
                c = getattr(f, "content", None)
                if c:
                    return base64.b64decode(c).decode("utf-8", "ignore")
            except Exception:
                pass

            return None

        content = (
            _read_text(getattr(self.provider.mr, "target_branch", None))
            or _read_text(getattr(self.provider.mr, "source_branch", None))
        )
        if not content:
            return {}

        parser = configparser.ConfigParser(
            delimiters=("=",),
            interpolation=None,
            inline_comment_prefixes=("#", ";"),
            strict=False,
        )
        try:
            parser.read_string(content)
        except Exception:
            return {}

        out: dict[str, str] = {}
        for section in parser.sections():
            if not section.lower().startswith("submodule"):
                continue
            path = parser.get(section, "path", fallback=None)
            url = parser.get(section, "url", fallback=None)
            if path and url:
                path = path.strip().strip('"').strip("'")
                url = url.strip().strip('"').strip("'")
                out[path] = url
        return out

    def _url_to_project_path(self, url: str) -> str | None:
        try:
            if url.startswith("git@") and ":" in url:
                path = url.split(":", 1)[1]
            else:
                path = urllib.parse.urlparse(url).path.lstrip("/")
            if path.endswith(".git"):
                path = path[:-4]
            return path or None
        except Exception:
            return None

    def _project_by_path(self, proj_path: str):
        if not proj_path:
            return None

        try:
            enc = urllib.parse.quote_plus(proj_path)
            return self.provider.gl.projects.get(enc)
        except Exception:
            pass

        try:
            return self.provider.gl.projects.get(proj_path)
        except Exception:
            pass

        try:
            name = proj_path.split("/")[-1]
            matches = self.provider.gl.projects.list(search=name, simple=True, membership=True, per_page=100)
            for p in matches:
                pwn = getattr(p, "path_with_namespace", "")
                if pwn.lower() == proj_path.lower():
                    return self.provider.gl.projects.get(p.id)
            if matches:
                get_logger().warning(f"[submodule] no exact match for {proj_path} (skip)")
        except Exception:
            pass

        return None

    def _compare_submodule(self, proj_path: str, old_sha: str, new_sha: str) -> list[dict]:
        key = (proj_path, old_sha, new_sha)
        if key in self._submodule_cache:
            return self._submodule_cache[key]
        try:
            proj = self._project_by_path(proj_path)
            if proj is None:
                get_logger().warning(f"[submodule] resolve failed for {proj_path}")
                self._submodule_cache[key] = []
                return []
            cmp = proj.repository_compare(old_sha, new_sha)
            if isinstance(cmp, dict):
                diffs = cmp.get("diffs", []) or []
            else:
                diffs = []
            self._submodule_cache[key] = diffs
            return diffs
        except Exception as e:
            get_logger().warning(f"[submodule] compare failed for {proj_path} {old_sha}..{new_sha}: {e}")
            self._submodule_cache[key] = []
            return []

    def expand_submodule_changes(self, changes: list[dict]) -> list[dict]:
        try:
            if not bool(get_settings().get("GITLAB.EXPAND_SUBMODULE_DIFFS", False)):
                return changes
        except Exception:
            return changes

        gitmodules = self._get_gitmodules_map()
        if not gitmodules:
            return changes

        out = list(changes)
        for ch in changes:
            patch = ch.get("diff") or ""
            if "Subproject commit" not in patch:
                continue

            old_m = re.search(r"^-Subproject commit ([0-9a-f]{7,40})", patch, re.M)
            new_m = re.search(r"^\+Subproject commit ([0-9a-f]{7,40})", patch, re.M)
            if not (old_m and new_m):
                continue
            old_sha, new_sha = old_m.group(1), new_m.group(1)

            sub_path = ch.get("new_path") or ch.get("old_path") or ""
            repo_url = gitmodules.get(sub_path)
            if not repo_url:
                get_logger().warning(f"[submodule] no url for '{sub_path}' in .gitmodules (skip)")
                continue

            proj_path = self._url_to_project_path(repo_url)
            if not proj_path:
                get_logger().warning(f"[submodule] cannot parse project path from url '{repo_url}' (skip)")
                continue

            get_logger().info(f"[submodule] {sub_path} url={repo_url} -> proj_path={proj_path}")
            sub_diffs = self._compare_submodule(proj_path, old_sha, new_sha)
            for sd in sub_diffs:
                sd_diff = sd.get("diff") or ""
                sd_old = sd.get("old_path") or sd.get("a_path") or ""
                sd_new = sd.get("new_path") or sd.get("b_path") or sd_old
                out.append({
                    "old_path": f"{sub_path}/{sd_old}" if sd_old else sub_path,
                    "new_path": f"{sub_path}/{sd_new}" if sd_new else sub_path,
                    "diff": sd_diff,
                    "new_file": sd.get("new_file", False),
                    "deleted_file": sd.get("deleted_file", False),
                    "renamed_file": sd.get("renamed_file", False),
                })
        return out
