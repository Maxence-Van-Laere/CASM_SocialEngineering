from flask import Flask, request, jsonify
import subprocess
import os
import json
import sys

app = Flask(__name__, static_folder='frontend', static_url_path='')

SCRIPT_MAP = {
    'Mastodon': 'social_media_scrapping/fetch_mastodon.py',
    'Bluesky': 'social_media_scrapping/fetch_bluesky.py',
    'Twitter (simulé)': 'social_media_scrapping/fetch_tweets.py'
}

CSV_MAP = {
    'Mastodon': 'social_media_data.csv',
    'Bluesky': 'social_media_data.csv',
    'Twitter (simulé)': 'tweets_raw.json'
}


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json(force=True)
    network = data.get('network')
    identifier = data.get('identifier')
    if not network or not identifier:
        return jsonify({'error': 'missing params'}), 400

    script = SCRIPT_MAP.get(network)
    if not script:
        return jsonify({'error': 'unknown network'}), 400

    env = os.environ.copy()
    env['PSEUDO'] = identifier

    try:
        proc = subprocess.run(['python', script], env=env, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'script timeout'}), 500

    # Print child's stdout/stderr to server console so print() in child is visible
    out = proc.stdout or ''
    err = proc.stderr or ''
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)

    # If the child script exited with non-zero, try to extract a friendly message
    if proc.returncode != 0:
        combined_all = ((out or '') + "\n" + (err or '')).strip()
        # Prefer a pretty-formatted error emitted by the script (starts with 'ERREUR')
        pretty = None
        if 'ERREUR :' in combined_all:
            pretty = combined_all[combined_all.find('ERREUR :'):].strip()
        elif 'Utilisateur introuvable' in combined_all:
            # older message fallback
            idx = combined_all.find('Utilisateur introuvable')
            pretty = combined_all[idx:idx+1000].strip()
        else:
            # fallback to stderr or stdout
            pretty = (err or out).strip() or f'Process exited with code {proc.returncode}'

        return jsonify({'error': pretty, 'stdout': out, 'stderr': err}), 400

    # After successful scraping, run the processing pipeline then the analyzer
    try:
        proc_pipeline = subprocess.run(['python', 'analyse_biais_IA/pipeline.py'], env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'pipeline timeout', 'stdout': out, 'stderr': err}), 500

    if proc_pipeline.stdout:
        print(proc_pipeline.stdout)
    if proc_pipeline.stderr:
        print(proc_pipeline.stderr, file=sys.stderr)

    if proc_pipeline.returncode != 0:
        return jsonify({'error': 'pipeline failed', 'stdout': proc_pipeline.stdout, 'stderr': proc_pipeline.stderr}), 400

    try:
        proc_analyzer = subprocess.run(['python', 'analyse_biais_IA/analyzer.py'], env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'analyzer timeout', 'stdout': proc_pipeline.stdout, 'stderr': proc_pipeline.stderr}), 500

    if proc_analyzer.stdout:
        print(proc_analyzer.stdout)
    if proc_analyzer.stderr:
        print(proc_analyzer.stderr, file=sys.stderr)

    if proc_analyzer.returncode != 0:
        return jsonify({'error': 'analyzer failed', 'stdout': proc_analyzer.stdout, 'stderr': proc_analyzer.stderr}), 400

    # Try to read produced CSV/JSON and extract messages
    messages = []
    csvfile = CSV_MAP.get(network)
    if csvfile and os.path.exists(csvfile):
        try:
            if csvfile.endswith('.csv'):
                import csv as _csv
                with open(csvfile, encoding='utf-8') as f:
                    reader = _csv.DictReader(f)
                    for row in reader:
                        msg = row.get('message') or row.get('text')
                        if msg:
                            messages.append(msg)
            elif csvfile.endswith('.json'):
                with open(csvfile, encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    msg = item.get('text') or item.get('message') or str(item)
                    messages.append(msg)
        except Exception as e:
            # ignore parsing errors, return stdout/stderr instead
            err += f"\nparse_error: {e}"

    return jsonify({'stdout': out, 'stderr': err, 'messages': messages})


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/final_report.json')
def serve_final_report():
    path = os.path.join(app.root_path,'analyse_biais_IA', 'output', 'final_report.json')
    if not os.path.exists(path):
        return jsonify({'error': 'final_report.json not found'}), 404
    try:
        with open(path, encoding='utf-8') as f:
            data = f.read()
        return app.response_class(data, mimetype='application/json')
    except Exception as e:
        return jsonify({'error': f'failed to read final_report.json: {e}'}), 500


@app.route('/schema.json')
def serve_schema():
    path = os.path.join(app.root_path, 'analyse_biais_IA', 'output', 'schema.json')
    if not os.path.exists(path):
        return jsonify({'error': 'schema.json not found'}), 404
    try:
        with open(path, encoding='utf-8') as f:
            data = f.read()
        return app.response_class(data, mimetype='application/json')
    except Exception as e:
        return jsonify({'error': f'failed to read schema.json: {e}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
