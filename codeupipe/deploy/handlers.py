"""
Serverless handler wrappers for platform-specific function signatures.

Each render function returns a Python source string that wraps a codeupipe
Pipeline as a serverless function handler compatible with the target platform.
Zero external dependencies — pure string template generation.
"""

__all__ = ["render_vercel_handler", "render_netlify_handler", "render_lambda_handler"]


def render_vercel_handler(pipeline_config_path: str = "pipeline.json") -> str:
    """Render a Vercel Python serverless function handler."""
    return (
        '"""Auto-generated Vercel serverless handler by cup deploy."""\n'
        "import asyncio\n"
        "import json\n"
        "from http.server import BaseHTTPRequestHandler\n"
        "from pathlib import Path\n"
        "\n"
        "from codeupipe import Pipeline, Payload\n"
        "from codeupipe.registry import default_registry\n"
        "\n"
        "\n"
        f'_CONFIG = Path(__file__).resolve().parent.parent / "{pipeline_config_path}"\n'
        "_pipeline = Pipeline.from_config(str(_CONFIG), registry=default_registry)\n"
        "\n"
        "\n"
        "class handler(BaseHTTPRequestHandler):\n"
        '    """Vercel serverless handler — inherits BaseHTTPRequestHandler."""\n'
        "\n"
        "    def do_POST(self):\n"
        "        length = int(self.headers.get('Content-Length', 0))\n"
        "        body = self.rfile.read(length) if length else b'{}'\n"
        "        data = json.loads(body)\n"
        "        result = asyncio.run(_pipeline.run(Payload(data)))\n"
        "        response = json.dumps(result.to_dict()).encode()\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-Type', 'application/json')\n"
        "        self.send_header('Access-Control-Allow-Origin', '*')\n"
        "        self.send_header('Content-Length', str(len(response)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(response)\n"
        "\n"
        "    def do_GET(self):\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-Type', 'application/json')\n"
        '        body = b\'{"status": "ok"}\'\n'
        "        self.send_header('Content-Length', str(len(body)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(body)\n"
        "\n"
        "    def do_OPTIONS(self):\n"
        "        self.send_response(204)\n"
        "        self.send_header('Access-Control-Allow-Origin', '*')\n"
        "        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')\n"
        "        self.send_header('Access-Control-Allow-Headers', 'Content-Type')\n"
        "        self.end_headers()\n"
    )


def render_netlify_handler(pipeline_config_path: str = "pipeline.json") -> str:
    """Render a Netlify Python serverless function handler."""
    return (
        '"""Auto-generated Netlify function handler by cup deploy."""\n'
        "import asyncio\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "from codeupipe import Pipeline, Payload\n"
        "from codeupipe.registry import default_registry\n"
        "\n"
        "\n"
        f'_CONFIG = Path(__file__).resolve().parent.parent / "{pipeline_config_path}"\n'
        "_pipeline = Pipeline.from_config(str(_CONFIG), registry=default_registry)\n"
        "\n"
        "\n"
        "def handler(event, context):\n"
        '    """Netlify function handler."""\n'
        "    body = event.get('body', '{}')\n"
        "    if event.get('isBase64Encoded'):\n"
        "        import base64\n"
        "        body = base64.b64decode(body).decode()\n"
        "    data = json.loads(body) if body else {}\n"
        "    result = asyncio.run(_pipeline.run(Payload(data)))\n"
        "    return {\n"
        "        'statusCode': 200,\n"
        "        'headers': {\n"
        "            'Content-Type': 'application/json',\n"
        "            'Access-Control-Allow-Origin': '*',\n"
        "        },\n"
        "        'body': json.dumps(result.to_dict()),\n"
        "    }\n"
    )


def render_lambda_handler(pipeline_config_path: str = "pipeline.json") -> str:
    """Render an AWS Lambda function handler."""
    return (
        '"""Auto-generated AWS Lambda handler by cup deploy."""\n'
        "import asyncio\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "from codeupipe import Pipeline, Payload\n"
        "from codeupipe.registry import default_registry\n"
        "\n"
        "\n"
        f'_CONFIG = Path(__file__).resolve().parent / "{pipeline_config_path}"\n'
        "_pipeline = Pipeline.from_config(str(_CONFIG), registry=default_registry)\n"
        "\n"
        "\n"
        "def handler(event, context):\n"
        '    """AWS Lambda handler — API Gateway proxy integration."""\n'
        "    body = event.get('body', '{}')\n"
        "    if event.get('isBase64Encoded'):\n"
        "        import base64\n"
        "        body = base64.b64decode(body).decode()\n"
        "    data = json.loads(body) if body else {}\n"
        "    result = asyncio.run(_pipeline.run(Payload(data)))\n"
        "    return {\n"
        "        'statusCode': 200,\n"
        "        'headers': {\n"
        "            'Content-Type': 'application/json',\n"
        "            'Access-Control-Allow-Origin': '*',\n"
        "            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',\n"
        "        },\n"
        "        'body': json.dumps(result.to_dict()),\n"
        "    }\n"
    )
