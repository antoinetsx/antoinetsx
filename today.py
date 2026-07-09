#!/usr/bin/env python3
"""
Génère un README GitHub façon neofetch, mis à jour automatiquement.
Récupère : repos, stars, commits, followers, langages, lignes de code (LOC).
"""

import os
import re
import time
import json
import datetime
import subprocess
import requests
from pathlib import Path
from xml.dom import minidom

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

USERNAME = os.environ.get("GITHUB_ACTOR", "Andrew6rant")
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]  # PAT stocké en secret (scope: repo, read:user)
HEADERS_GQL = {"Authorization": f"bearer {ACCESS_TOKEN}"}
HEADERS_REST = {"Authorization": f"token {ACCESS_TOKEN}"}

BASE = Path(__file__).parent
CACHE_DIR = BASE / "cache"
CACHE_DIR.mkdir(exist_ok=True)
LOC_CACHE_FILE = CACHE_DIR / f"{USERNAME}_loc.json"
REPO_ARCHIVE_FILE = CACHE_DIR / "repository_archive.txt"

QUERY_COUNT = {"user_getter": 0, "follower": 0, "graph_repos_stars": 0,
               "recursive_loc": 0, "graph_commits": 0, "loc_query": 0}


# ---------------------------------------------------------------------------
# GraphQL / REST helpers
# ---------------------------------------------------------------------------

def query_gql(generated_query):
    """Requête générique vers l'API GraphQL GitHub."""
    request = requests.post("https://api.github.com/graphql",
                             json={"query": generated_query}, headers=HEADERS_GQL)
    if request.status_code == 200:
        return request.json()
    raise Exception(f"GraphQL query failed: {request.status_code} - {generated_query}")


def user_getter(username):
    """Retourne l'id GitHub de l'utilisateur + sa date de création de compte."""
    QUERY_COUNT["user_getter"] += 1
    query = f"""{{
        user(login: "{username}") {{
            id
            createdAt
        }}
    }}"""
    request = query_gql(query)
    return {"id": request["data"]["user"]["id"]}, request["data"]["user"]["createdAt"]


def follower_getter(username):
    QUERY_COUNT["follower"] += 1
    query = f"""{{
        user(login: "{username}") {{
            followers {{
                totalCount
            }}
        }}
    }}"""
    request = query_gql(query)
    return int(request["data"]["user"]["followers"]["totalCount"])


def graph_repos_stars(count_type, owner_affiliation, cursor=None):
    """Retourne soit le nombre de repos, soit le total de stars."""
    QUERY_COUNT["graph_repos_stars"] += 1
    query = f"""{{
        user(login: "{USERNAME}") {{
            repositories(first: 100, after: {"null" if cursor is None else f'"{cursor}"'},
                ownerAffiliations: {owner_affiliation}) {{
                totalCount
                edges {{
                    node {{
                        ... on Repository {{
                            nameWithOwner
                            stargazers {{
                                totalCount
                            }}
                        }}
                    }}
                }}
                pageInfo {{
                    endCursor
                    hasNextPage
                }}
            }}
        }}
    }}"""
    request = query_gql(query)
    if count_type == "repos":
        return request["data"]["user"]["repositories"]["totalCount"]
    elif count_type == "stars":
        return stars_counter(request["data"]["user"]["repositories"]["edges"])


def stars_counter(data):
    total = 0
    for node in data:
        total += node["node"]["stargazers"]["totalCount"]
    return total


def graph_commits(start_date, end_date):
    """Nombre de commits sur une période donnée (contributionsCollection)."""
    QUERY_COUNT["graph_commits"] += 1
    query = f"""{{
        user(login: "{USERNAME}") {{
            contributionsCollection(from: "{start_date}", to: "{end_date}") {{
                contributionCalendar {{
                    totalContributions
                }}
            }}
        }}
    }}"""
    request = query_gql(query)
    return int(request["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"])


def total_commits():
    """Additionne les contributions année par année depuis la création du compte."""
    _, created_at = user_getter(USERNAME)
    created_year = int(created_at[:4])
    current_year = datetime.datetime.now().year
    total = 0
    for year in range(created_year, current_year + 1):
        start = f"{year}-01-01T00:00:00Z"
        end = f"{year}-12-31T23:59:59Z"
        try:
            total += graph_commits(start, end)
        except Exception:
            pass
    return total


# ---------------------------------------------------------------------------
# LOC via clonage des repos (avec cache pour ne pas tout refaire)
# ---------------------------------------------------------------------------

def query_repo_list():
    """Liste tous les repos (owner + collaborator + org member) via REST, pagination incluse."""
    repos = []
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/user/repos?per_page=100&page={page}&affiliation=owner,collaborator,organization_member",
            headers=HEADERS_REST)
        data = r.json()
        if not data or "message" in data and page == 1 and not isinstance(data, list):
            break
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def load_loc_cache():
    if LOC_CACHE_FILE.exists():
        return json.loads(LOC_CACHE_FILE.read_text())
    return {}


def save_loc_cache(cache):
    LOC_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def repo_loc(repo, cache):
    """Clone (shallow) un repo et calcule les lignes ajoutées/supprimées de l'utilisateur.
    Utilise le cache basé sur le dernier commit connu pour éviter de re-cloner à chaque run."""
    full_name = repo["full_name"]
    default_branch = repo.get("default_branch", "main")

    cached = cache.get(full_name)
    # On ne recalcule que si pas de cache (simplification : cache "à vie" tant que le repo existe)
    if cached is not None:
        return cached["additions"], cached["deletions"]

    clone_dir = Path(f"/tmp/loc_clone/{full_name.replace('/', '_')}")
    added, deleted = 0, 0
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--single-branch", f"--branch={default_branch}",
             f"https://x-access-token:{ACCESS_TOKEN}@github.com/{full_name}.git", str(clone_dir)],
            check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        result = subprocess.run(
            ["git", "log", "--author", USERNAME, "--pretty=tformat:", "--numstat"],
            cwd=clone_dir, capture_output=True, text=True, timeout=60)

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                a, d, _ = parts
                if a.isdigit():
                    added += int(a)
                if d.isdigit():
                    deleted += int(d)
    except Exception:
        pass
    finally:
        subprocess.run(["rm", "-rf", str(clone_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cache[full_name] = {"additions": added, "deletions": deleted}
    return added, deleted


def compute_total_loc():
    """Calcule le total des lignes ajoutées/supprimées sur tous les repos accessibles.
    Résultat mis en cache par repo pour limiter le temps de build."""
    cache = load_loc_cache()
    repos = query_repo_list()
    total_added, total_deleted = 0, 0
    for repo in repos:
        if repo.get("fork"):
            continue
        a, d = repo_loc(repo, cache)
        total_added += a
        total_deleted += d
    save_loc_cache(cache)
    net = total_added - total_deleted
    return total_added, total_deleted, net


# ---------------------------------------------------------------------------
# Langages les plus utilisés
# ---------------------------------------------------------------------------

def top_languages(limit=5):
    query = f"""{{
        user(login: "{USERNAME}") {{
            repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {{
                edges {{
                    node {{
                        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                            edges {{
                                size
                                node {{
                                    name
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}"""
    request = query_gql(query)
    totals = {}
    for edge in request["data"]["user"]["repositories"]["edges"]:
        for lang_edge in edge["node"]["languages"]["edges"]:
            name = lang_edge["node"]["name"]
            totals[name] = totals.get(name, 0) + lang_edge["size"]
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    grand_total = sum(totals.values()) or 1
    return [(name, size / grand_total * 100) for name, size in ranked[:limit]]


# ---------------------------------------------------------------------------
# Uptime (âge du compte GitHub, façon "neofetch")
# ---------------------------------------------------------------------------

def account_age_string():
    _, created_at = user_getter(USERNAME)
    created = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    now = datetime.datetime.utcnow()
    delta_days = (now - created).days
    years = delta_days // 365
    remaining = delta_days % 365
    months = remaining // 30
    days = remaining % 30
    return f"{years} years, {months} months, {days} days"


# ---------------------------------------------------------------------------
# Génération des SVG
# ---------------------------------------------------------------------------

def format_number(n):
    return f"{n:,}"


def justify_line(label, value, total_width=45):
    """Aligne 'label' + points + 'value' comme dans un neofetch."""
    dots = "." * max(2, total_width - len(label) - len(value))
    return f"{label}{dots}{value}"


def render_svg(theme, stats):
    """theme: 'dark' ou 'light'. Lit le template (.svg.tpl) et écrit le SVG final (.svg)."""
    template_path = BASE / f"{theme}_mode.svg.tpl"
    svg = template_path.read_text()
    for key, value in stats.items():
        svg = svg.replace(f"{{{{{key}}}}}", str(value))
    output_path = BASE / f"{theme}_mode.svg"
    output_path.write_text(svg)


def svg_overwrite(theme, stats):
    """Charge le squelette, injecte les <text> dynamiques."""
    render_svg(theme, stats)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Collecte des stats GitHub...")

    repos = graph_repos_stars("repos", "[OWNER]")
    stars = graph_repos_stars("stars", "[OWNER]")
    followers = follower_getter(USERNAME)
    commits = total_commits()
    added, deleted, net = compute_total_loc()
    langs = top_languages()
    uptime = account_age_string()

    lang_lines = []
    for i, (name, pct) in enumerate(langs):
        lang_lines.append(f"{name} {pct:.1f}%")

    stats = {
        "USERNAME": USERNAME,
        "REPOS": format_number(repos),
        "STARS": format_number(stars),
        "COMMITS": format_number(commits),
        "FOLLOWERS": format_number(followers),
        "LOC_ADDED": format_number(added),
        "LOC_DELETED": format_number(deleted),
        "LOC_NET": format_number(net),
        "UPTIME": uptime,
        "TOP_LANG_1": lang_lines[0] if len(lang_lines) > 0 else "",
        "TOP_LANG_2": lang_lines[1] if len(lang_lines) > 1 else "",
        "TOP_LANG_3": lang_lines[2] if len(lang_lines) > 2 else "",
        "TOP_LANG_4": lang_lines[3] if len(lang_lines) > 3 else "",
        "TOP_LANG_5": lang_lines[4] if len(lang_lines) > 4 else "",
        "LAST_UPDATED": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    print(json.dumps(stats, indent=2, ensure_ascii=False))

    for theme in ("dark", "light"):
        svg_overwrite(theme, stats)

    print("SVG générés avec succès.")


if __name__ == "__main__":
    main()
