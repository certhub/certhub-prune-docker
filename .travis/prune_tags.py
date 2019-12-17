#!/usr/bin/env python3
#
# usage:
# python3 .travis/prune_tags.py org/repo tag-pattern

import dateparser
import fnmatch
import json
import os
import sys

from http.client import HTTPSConnection
from datetime import datetime, timezone


def login(repo, username, password):
    """
    Sign into the dockerhub web UI and return JWT token.
    """

    url = "https://hub.docker.com/v2/users/login/"
    headers = {"Content-Type": "application/json"}
    body = {"username": username, "password": password}

    client = HTTPSConnection("hub.docker.com")
    client.request("POST", url, body=json.dumps(body), headers=headers)
    resp = client.getresponse()
    assert resp.status == 200

    return json.load(resp).get('token')


def delete_tag(tag, repo, token):
    """
    Delete the specified tag from the given repo
    """

    client = HTTPSConnection("hub.docker.com")
    url = "https://hub.docker.com/v2/repositories/{:s}/tags/{:s}/".format(repo, tag['name'])
    headers = {
        "Accept": "application/json",
        "Authorization": "JWT {:s}".format(token),
    }

    client.request("DELETE", url, headers=headers)
    resp = client.getresponse()
    assert resp.status == 204


def list_tags(repo, token):
    client = HTTPSConnection("hub.docker.com")
    url = "https://hub.docker.com/v2/repositories/{:s}/tags/".format(repo)
    headers = {
        "Accept": "application/json",
        "Authorization": "JWT {:s}".format(token),
    }

    while True:
        client.request("GET", url, headers=headers)
        resp = client.getresponse()
        assert resp.status == 200

        page = json.load(resp)

        for tag in page.get('results', []):
            yield tag

        url = page.get('next', None)
        if url is None:
            break


def tag_name_predicate(pattern):
    """
    Returns a filter function for tags matching the given fnmatch pattern.
    """

    return lambda tag: fnmatch.fnmatch(tag['name'], pattern)


def tag_notafter_predicate(deadline):
    """
    Returns a filter function for tags updated before the given deadline.
    """

    return lambda tag: dateparser.parse(tag['last_updated']) < notafter


if __name__ == '__main__':
    repo = sys.argv[1]
    pattern = sys.argv[2]
    notafter = dateparser.parse(sys.argv[3], settings={
        'RELATIVE_BASE': datetime.now(timezone.utc),
        'RETURN_AS_TIMEZONE_AWARE': True
    })

    username = os.environ.get('DOCKER_USERNAME')
    password = os.environ.get('DOCKER_PASSWORD')

    name_predicate = tag_name_predicate(pattern)
    date_predicate = tag_notafter_predicate(notafter)

    token = login(repo, username, password)
    tags = list_tags(repo, token)
    filtered_tags = list(filter(name_predicate, filter(date_predicate, tags)))

    for tag in filtered_tags:
        delete_tag(tag, repo, token)
