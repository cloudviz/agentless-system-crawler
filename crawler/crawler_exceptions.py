#!/usr/bin/python
# -*- coding: utf-8 -*-


class CrawlError(Exception):

    """Indicates that a crawl timed out."""

    pass


class CrawlTimeoutError(Exception):

    """Indicates some error during crawling."""

    pass
