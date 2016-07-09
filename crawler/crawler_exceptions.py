#!/usr/bin/python
# -*- coding: utf-8 -*-


class CrawlError(Exception):

    """Indicates that a crawl timed out."""

    pass


class CrawlTimeoutError(CrawlError):

    """Indicates some error during crawling."""

    pass


class ContainerInvalidEnvironment(Exception):

    """"Indicates that the environment can not be applied to the operation."""

    pass


class AlchemyInvalidMetadata(ContainerInvalidEnvironment):

    """Invalid or non-present alchemy metadata file."""

    pass


class AlchemyInvalidContainer(ContainerInvalidEnvironment):

    """Invalid or non-present alchemy metadata file."""

    pass


class RuntimeEnvironmentPluginNotFound(Exception):

    """Invalid or non-present plugin for the given environment."""

    pass
