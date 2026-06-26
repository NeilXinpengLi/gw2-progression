"""Analyze ontology implementation maturity."""
import ast, os

ont_dir = "src/gw2_progression/ontology"
files = [f for f in os.listdir(ont_dir) if f.endswith(".py") and f != "__init__.py"]

total_lines = 0
total_functions = 0
total_classes = 0
total_async_funcs = 0
docstring_modules = 0
classes = {}
funcs = {}

for fname in sorted(files):
    path = os.path.join(ont_dir, fname)
    with open(path) as f:
        source = f.read()
    lines = len(source.splitlines())
    total_lines += lines

    tree = ast.parse(source)
    has_docstring = ast.get_docstring(tree) is not None
    if has_docstring:
        docstring_modules += 1

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            total_classes += 1
            classes[fname] = classes.get(fname, 0) + 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total_functions += 1
            funcs[fname] = funcs.get(fname, 0) + 1
            if isinstance(node, ast.AsyncFunctionDef):
                total_async_funcs += 1

print(f"Total ontology: {len(files)} modules, {total_lines} lines")
print(f"  Functions: {total_functions} ({total_async_funcs} async)")
print(f"  Classes: {total_classes}")
print(f"  Modules with docstrings: {docstring_modules}/{len(files)}")
print()
for fname in sorted(files):
    print(f"  {fname}: {classes.get(fname,0)} classes, {funcs.get(fname,0)} funcs")

print()
with open("src/gw2_progression/database.py") as f:
    db_src = f.read()
print(f"Ontology DB tables: {db_src.count('CREATE TABLE IF NOT EXISTS ontology_')}")
print(f"Ontology references in database.py: {db_src.count('ontology_')}")

for svc in ["snapshot_service.py", "goal_service.py", "report_generator.py", "build_service.py"]:
    path = f"src/gw2_progression/services/{svc}"
    with open(path) as f:
        content = f.read()
    ont_refs = content.count("ontology")
    import_lines = [l for l in content.splitlines() if "ontology" in l.lower() and ("import" in l.lower() or "from" in l.lower())]
    print(f"\n{svc}: {ont_refs} ontology refs")
    for l in import_lines:
        print(f"    {l.strip()}")

# Coverage analysis
print("\n--- Coverage Gaps ---")
print("Legendary do-not-sell: ACCOUNTS COVERED" if os.path.exists("src/gw2_progression/ontology/account_mapper.py") else "MISSING")
print("Build trust: COVERED" if os.path.exists("src/gw2_progression/ontology/build_trust.py") else "MISSING")
print("Report mapper: COVERED" if os.path.exists("src/gw2_progression/ontology/report_mapper.py") else "MISSING")
print("Market domain: NOT COVERED (Phase D)")
print("AI agent integration: NOT COVERED (Phase D)")
print("Object UI / Inspector: NOT COVERED (Phase D)")
print("RDF/OWL export: NOT COVERED (intentionally skipped per doc)")
