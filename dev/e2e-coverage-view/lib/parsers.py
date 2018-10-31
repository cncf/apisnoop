import re
import json
import os

import requests

import hashlib

from urlparse import urlparse
from collections import defaultdict

__all__ = ['load_openapi_spec', 'load_audit_log', 'find_openapi_entry']


def load_swagger_file(url, cache=False):
    """Load a swagger file from path or URL"""
    url_parsed = urlparse(url)
    if url_parsed.scheme in ['http', 'https']:
        if cache:
            # Use HEAD request to get the etag of the URL (assuming github here)
            # This helps when master changes but the url doesnt change
            head = requests.head(url)
            key = head.headers.get('etag')
            if key:
                key = key.strip('"')
            else:
                # Fall back to old way of doing things
                key = hashlib.md5(url).hexdigest()
            if not os.path.exists('cache'):
                os.mkdir('cache')
            cache_path = os.path.join('cache', "swagger_%s.json" % key)
            if not os.path.exists(cache_path):
                swagger = requests.get(url).json()
                with open(cache_path, "wb") as f:
                    json.dump(swagger, f)
            else:
                with open(cache_path, "rb") as f:
                    swagger = json.load(f)
        else:
            swagger = requests.get(url).json()
    else: # treat as file on disk
        with open(url, "rb") as f:
            swagger = json.load(f)
    return swagger


# k8s appears to allow/expect a trailing {path} variable to capture everything
# remaining in the path, including '/' characters, which doesn't appear to be
# allowed according to the openapi 2.0 or 3.0 specs
# (ref: https://github.com/OAI/OpenAPI-Specification/issues/892)
K8S_PATH_VARIABLE_PATTERN = re.compile("{(path)}$")
VARIABLE_PATTERN = re.compile("{([^}]+)}")
def compile_path_regex(path):
    # first replace the special trailing {path} wildcard with a named regex
    path_regex = K8S_PATH_VARIABLE_PATTERN.sub("(?P<\\1>.+)", path).rstrip('/')
    # replace wildcards in {varname} format to a named regex
    path_regex = VARIABLE_PATTERN.sub("(?P<\\1>[^/]+)", path_regex).rstrip('/')
    # TODO(spiffxp): unsure if trailing / _should_ be counted toward /proxy
    if path_regex.endswith("proxy"): # allow proxy to catch a trailing /
        path_regex += "/?$"
    else:
        path_regex += "$"
    print 'Converted path: %s into path_regex: %s' % (path, path_regex)
    return path_regex


LEVEL_PATTERN = re.compile("/v(?P<api_version>[0-9]+)(?:(?P<api_level>alpha|beta)(?P<api_level_version>[0-9]+))?")
def parse_level_from_path(path):
    # get the level (alpha/beta/stable) and the version from the path
    level = None
    match = LEVEL_PATTERN.search(path)
    if match:
        level = match.groupdict().get("api_level")
    if level is None:
        level = "stable"
    return level


def load_openapi_spec(url):
    # try:
    openapi_spec = {}

    swagger = load_swagger_file(url, cache=True)
    openapi_spec['paths'] = {}
    openapi_spec['prefix_cache'] = defaultdict(dict)
    openapi_spec['hit_cache'] = {}

    for path in swagger['paths']:
        path_regex = compile_path_regex(path)

        path_data = {}
        path_data['path'] = path
        path_data['level'] = parse_level_from_path(path)
        # methods
        path_data['methods'] = {}
        for method, swagger_method in swagger['paths'][path].items():
            if method == "parameters":
                continue
            if 'deprecated' in swagger_method.get('description', '').lower():
                print 'Skipping deprecated endpoint %s %s' % (method, path)
                continue
            produces = swagger_method.get('produces', [])
            can_watch = ('application/json;stream=watch' in produces or
                         'application/vnd.kubernetes.protobuf;stream=watch' in produces)
            must_watch = swagger_method.get('x-kubernetes-action') == 'watch'
            if must_watch:
                print("must watch " + path)
            method_data = {}
            tags = sorted(swagger_method.get('tags', list()))
            if len(tags) > 0:
                method_data['tags'] = tags
                tag = tags[0]
                # just use one tag for category
                category = tag.split("_")[0]
                method_data['category'] = category
            else:
                method_data['category'] = ''
            # todo - request + response
            if not must_watch:
                path_data['methods'][method] = method_data
            if can_watch:
                path_data['methods']['watch'] = method_data
        # use the path regex as the key so that we search for a match easily
        openapi_spec['paths'][path_regex] = path_data

        # crazy caching using prefixes
        bits = path.strip("/").split("/", 2)
        if bits[0] in ["apis", "api"] and len(bits) > 1:
            openapi_spec['prefix_cache']["/" + "/".join(bits[0:2])][path_regex] = path_data
        else:
            openapi_spec['prefix_cache'][None][path_regex] = path_data
        # print path, path_regex, re.match(path_regex, path.rstrip('/')) is not None
    return openapi_spec

    # except Exception as e:
    #     print("Failed to load openapi spec \"%s\"" % url)
    #     raise e


def load_audit_log(path):
    audit_log = []
    with open(path, "rb") as logfile:
        for entry in logfile:
            raw_event = json.loads(entry)
            # TODO(spiffxp): the audit log verb is empty when we HEAD or OPTIONS some k8s endpoints
            # translate the audit log 'verb' into a corresponding openapi 'method'
            verb_tt = {
                'get': ['get', 'list', 'proxy'],
                'patch': ['patch'],
                'put': ['update'],
                'post': ['create'],
                'delete': ['delete', 'deletecollection'],
                'watch': ['watch', 'watchlist'],
            }

            for method, verbs in verb_tt.items():
                if raw_event['verb'] in verbs:
                    raw_event['method'] = method
                    break
            if "method" not in raw_event:
                print("Error parsing event - HTTP method map not defined at \"%s\" for verb \"%s\"" % (raw_event['requestURI'], raw_event['verb']))

            audit_log.append(raw_event)
    return audit_log


def find_openapi_entry(openapi_spec, event):
    url = urlparse(event['requestURI'])
    hit_cache = openapi_spec['hit_cache']
    prefix_cache = openapi_spec['prefix_cache']
    # 1) Cached seen before results
    if url.path in hit_cache:
        return hit_cache[url.path]
    # 2) Indexed by prefix patterns to cut down search time
    for prefix in prefix_cache:
        if prefix is not None and url.path.startswith(prefix):
            paths = prefix_cache[prefix]
            break
    else:
        paths = prefix_cache[None]

    for regex in paths:
        if re.match(regex, url.path):
            hit_cache[url.path] = openapi_spec['paths'][regex]
            return openapi_spec['paths'][regex]
        elif re.search(regex, event['requestURI']):
            print("Incomplete match", regex, event['requestURI'])
    # cache failures too
    hit_cache[url.path] = None
    return None
