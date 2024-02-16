# Python Version: 3.x
# -*- coding: utf-8 -*-
"""
the module for Aizu Online Judge (http://judge.u-aizu.ac.jp/onlinejudge/)

:note: There is the offcial API http://developers.u-aizu.ac.jp/index
"""

import json
import re
import string
import urllib.parse
from logging import getLogger
from typing import *

import bs4
import requests

import onlinejudge._implementation.testcase_zipper
import onlinejudge._implementation.utils as utils
import onlinejudge.type
from onlinejudge.type import TestCase

logger = getLogger(__name__)


class AOJService(onlinejudge.type.Service):
    def get_url(self) -> str:
        return 'http://judge.u-aizu.ac.jp/onlinejudge/'

    def get_name(self) -> str:
        return 'Aizu Online Judge'

    @classmethod
    def from_url(cls, url: str) -> Optional['AOJService']:
        # example: http://judge.u-aizu.ac.jp/onlinejudge/
        # example: https://onlinejudge.u-aizu.ac.jp/home
        result = urllib.parse.urlparse(url)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc in ('judge.u-aizu.ac.jp', 'onlinejudge.u-aizu.ac.jp'):
            return cls()
        return None

    # TODO: Logging in via this URL doesn't work with Selenium. why?
    # def get_url_of_login_page(self) -> str:
    #     return 'https://onlinejudge.u-aizu.ac.jp/signin'

    def is_logged_in(self, *, session: Optional[requests.Session] = None) -> bool:
        session = session or utils.get_default_session()
        url = 'https://judgeapi.u-aizu.ac.jp/self'
        resp = utils.request('GET', url, session=session, raise_for_status=False)
        if resp.status_code != 200:
            return False
        data = json.loads(resp.content)
        logger.debug('self: %s', resp.content)
        return 'id' in data


class AOJProblem(onlinejudge.type.Problem):
    """
    :ivar problem_id: :py:class:`str` like `DSL_1_A` or `2256`
    """
    def __init__(self, *, problem_id):
        self.problem_id = problem_id

    def download_sample_cases(self, *, session: Optional[requests.Session] = None) -> List[TestCase]:
        session = session or utils.get_default_session()

        # get samples via the official API
        # reference: http://developers.u-aizu.ac.jp/api?key=judgedat%2Ftestcases%2Fsamples%2F%7BproblemId%7D_GET
        url = 'https://judgedat.u-aizu.ac.jp/testcases/samples/{}'.format(self.problem_id)
        resp = utils.request('GET', url, session=session)
        samples = []  # type: List[TestCase]
        for i, sample in enumerate(json.loads(resp.text)):
            samples += [TestCase(
                'sample-{}'.format(i + 1),
                str(sample['serial']),
                sample['in'].encode(),
                str(sample['serial']),
                sample['out'].encode(),
            )]

        # parse HTML if no samples are registered
        # see: https://github.com/kmyk/online-judge-tools/issues/207
        if not samples:
            logger.warning("sample cases are not registered in the official API")
            logger.info("fallback: parsing HTML")

            # reference: http://developers.u-aizu.ac.jp/api?key=judgeapi%2Fresources%2Fdescriptions%2F%7Blang%7D%2F%7Bproblem_id%7D_GET
            url = 'https://judgeapi.u-aizu.ac.jp/resources/descriptions/ja/{}'.format(self.problem_id)
            resp = utils.request('GET', url, session=session)
            html = json.loads(resp.text)['html']

            # list h3+pre
            zipper = onlinejudge._implementation.testcase_zipper.SampleZipper()
            expected_strings = ('入力例', '出力例', 'Sample Input', 'Sample Output')
            soup = bs4.BeautifulSoup(html, utils.HTML_PARSER)
            for pre in soup.find_all('pre'):
                tag = pre.find_previous_sibling()
                if tag and tag.name == 'h3' and tag.string and any(s in tag.string for s in expected_strings):
                    s = utils.textfile(utils.parse_content(pre).lstrip())
                    zipper.add(s.encode(), tag.string)
            samples = zipper.get()

        return samples

    def download_system_cases(self, *, session: Optional[requests.Session] = None) -> List[TestCase]:
        session = session or utils.get_default_session()

        # get header
        # reference: http://developers.u-aizu.ac.jp/api?key=judgedat%2Ftestcases%2F%7BproblemId%7D%2Fheader_GET
        url = 'https://judgedat.u-aizu.ac.jp/testcases/{}/header'.format(self.problem_id)
        resp = utils.request('GET', url, session=session)
        header = json.loads(resp.text)

        # get testcases via the official API
        testcases = []  # type: List[TestCase]
        for header in header['headers']:
            # NOTE: the endpoints are not same to http://developers.u-aizu.ac.jp/api?key=judgedat%2Ftestcases%2F%7BproblemId%7D%2F%7Bserial%7D_GET since the json API often says "..... (terminated because of the limitation)"
            # NOTE: even when using https://judgedat.u-aizu.ac.jp/testcases/PROBLEM_ID/SERIAL, there is the 1G limit (see https://twitter.com/beet_aizu/status/1194947611100188672)
            url = 'https://judgedat.u-aizu.ac.jp/testcases/{}/{}'.format(self.problem_id, header['serial'])
            resp_in = utils.request('GET', url + '/in', session=session)
            resp_out = utils.request('GET', url + '/out', session=session)
            testcases += [TestCase(
                header['name'],
                header['name'],
                resp_in.content,
                header['name'],
                resp_out.content,
            )]
        return testcases

    def get_url(self) -> str:
        return 'http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id={}'.format(self.problem_id)

    @classmethod
    def from_url(cls, url: str) -> Optional['AOJProblem']:
        result = urllib.parse.urlparse(url)

        # example: http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=1169
        # example: http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=DSL_1_A&lang=jp
        querystring = urllib.parse.parse_qs(result.query)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc == 'judge.u-aizu.ac.jp' \
                and utils.normpath(result.path) == '/onlinejudge/description.jsp' \
                and querystring.get('id') \
                and len(querystring['id']) == 1:
            n, = querystring['id']
            return cls(problem_id=n)

        # example: https://onlinejudge.u-aizu.ac.jp/challenges/sources/JAG/Prelim/2881
        # example: https://onlinejudge.u-aizu.ac.jp/courses/library/4/CGL/3/CGL_3_B
        m = re.match(r'^/(challenges|courses)/(sources|library/\d+|lesson/\d+)/(\w+)/(\w+)/(\w+)$', utils.normpath(result.path))
        if result.scheme in ('', 'http', 'https') \
                and result.netloc == 'onlinejudge.u-aizu.ac.jp' \
                and m:
            n = m.group(5)
            return cls(problem_id=n)

        # example: https://onlinejudge.u-aizu.ac.jp/problems/0423
        # example: https://onlinejudge.u-aizu.ac.jp/problems/CGL_3_B
        m = re.match(r'^/problems/(\w+)$', utils.normpath(result.path))
        if result.scheme in ('', 'http', 'https') \
                and result.netloc == 'onlinejudge.u-aizu.ac.jp' \
                and m:
            n = m.group(1)
            return cls(problem_id=n)

        return None

    def get_service(self) -> AOJService:
        return AOJService()


class AOJArenaProblem(onlinejudge.type.Problem):
    """
    :ivar arena_id: :py:class:`str`. for example, `RitsCamp19Day2`
    :ivar alphabet: :py:class:`str`

    .. versionadded:: 6.1.0
    """
    def __init__(self, *, arena_id, alphabet):
        assert alphabet in string.ascii_uppercase
        self.arena_id = arena_id
        self.alphabet = alphabet

        self._problem_id = None  # Optional[str]

    def get_problem_id(self, *, session: Optional[requests.Session] = None) -> str:
        """
        :note: use http://developers.u-aizu.ac.jp/api?key=judgeapi%2Farenas%2F%7BarenaId%7D%2Fproblems_GET
        """

        if self._problem_id is None:
            session = session or utils.get_default_session()
            url = 'https://judgeapi.u-aizu.ac.jp/arenas/{}/problems'.format(self.arena_id)
            resp = utils.request('GET', url, session=session)
            problems = json.loads(resp.text)
            for problem in problems:
                if problem['id'] == self.alphabet:
                    self._problem_id = problem['problemId']
                    logger.debug('problem: %s', problem)
                    break
        return self._problem_id

    def download_sample_cases(self, *, session: Optional[requests.Session] = None) -> List[TestCase]:
        return AOJProblem(problem_id=self.get_problem_id()).download_sample_cases(session=session)

    def download_system_cases(self, *, session: Optional[requests.Session] = None) -> List[TestCase]:
        return AOJProblem(problem_id=self.get_problem_id()).download_system_cases(session=session)

    def download_content(self, *, session: Optional[requests.Session] = None):
        """
        :raise NotImplementedError:
        """
        raise NotImplementedError

    def get_url(self) -> str:
        return 'https://onlinejudge.u-aizu.ac.jp/services/room.html#{}/problems/{}'.format(self.arena_id, self.alphabet)

    @classmethod
    def from_url(cls, url: str) -> Optional['AOJArenaProblem']:
        # example: https://onlinejudge.u-aizu.ac.jp/services/room.html#RitsCamp19Day2/problems/A
        result = urllib.parse.urlparse(url)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc == 'onlinejudge.u-aizu.ac.jp' \
                and utils.normpath(result.path) == '/services/room.html':
            fragment = result.fragment.split('/')
            if len(fragment) == 3 and fragment[1] == 'problems':
                return cls(arena_id=fragment[0], alphabet=fragment[2].upper())
        return None

    def get_service(self) -> AOJService:
        return AOJService()


onlinejudge.dispatch.services += [AOJService]
onlinejudge.dispatch.problems += [AOJProblem, AOJArenaProblem]
