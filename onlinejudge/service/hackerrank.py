# Python Version: 3.x
"""
the module for HackerRank (https://www.hackerrank.com/)
"""

import json
import re
import urllib.parse
from logging import getLogger
from typing import *

import bs4
import requests

import onlinejudge._implementation.testcase_zipper
import onlinejudge._implementation.utils as utils
import onlinejudge.dispatch
import onlinejudge.type
from onlinejudge.type import *

logger = getLogger(__name__)


class HackerRankService(onlinejudge.type.Service):
    def get_url_of_login_page(self) -> str:
        return 'https://www.hackerrank.com/auth/login'

    def is_logged_in(self, *, session: Optional[requests.Session] = None) -> bool:
        session = session or utils.get_default_session()
        url = 'https://www.hackerrank.com/auth/login'
        resp = utils.request('GET', url, session=session)
        return '/auth' not in resp.url

    def get_url(self) -> str:
        return 'https://www.hackerrank.com/'

    def get_name(self) -> str:
        return 'HackerRank'

    @classmethod
    def from_url(cls, url: str) -> Optional['HackerRankService']:
        # example: https://www.hackerrank.com/dashboard
        result = urllib.parse.urlparse(url)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc in ('hackerrank.com', 'www.hackerrank.com'):
            return cls()
        return None


class HackerRankProblem(onlinejudge.type.Problem):
    """
    :ivar contest_slug: :py:class:`str`; this is not `contest_id` because HackerRank itself says this as `contest_slug` in a JSON for submissions.
    :ivar challenge_slug: :py:class:`str`
    """
    def __init__(self, contest_slug: str, challenge_slug: str):
        self.contest_slug = contest_slug
        self.challenge_slug = challenge_slug

    def download_sample_cases(self, *, session: Optional[requests.Session] = None) -> List[TestCase]:
        return self.download_system_cases(session=session)

    def download_system_cases(self, *, session: Optional[requests.Session] = None) -> List[TestCase]:
        session = session or utils.get_default_session()
        # example: https://www.hackerrank.com/rest/contests/hourrank-1/challenges/beautiful-array/download_testcases
        url = 'https://www.hackerrank.com/rest/contests/{}/challenges/{}/download_testcases'.format(self.contest_slug, self.challenge_slug)
        resp = utils.request('GET', url, session=session, raise_for_status=False)
        if resp.status_code == 403:
            logger.debug('HTML: %s', resp.content.decode())
            raise onlinejudge.type.SampleParseError("Access Denied. Did you set your User-Agent?")
        resp.raise_for_status()
        return onlinejudge._implementation.testcase_zipper.extract_from_zip(resp.content, '%eput/%eput%s.txt')

    def get_url(self) -> str:
        if self.contest_slug == 'master':
            return 'https://www.hackerrank.com/challenges/{}'.format(self.challenge_slug)
        else:
            return 'https://www.hackerrank.com/contests/{}/challenges/{}'.format(self.contest_slug, self.challenge_slug)

    def get_service(self) -> HackerRankService:
        return HackerRankService()

    @classmethod
    def from_url(cls, url: str) -> Optional['HackerRankProblem']:
        # example: https://www.hackerrank.com/contests/university-codesprint-2/challenges/the-story-of-a-tree
        # example: https://www.hackerrank.com/challenges/fp-hello-world
        result = urllib.parse.urlparse(url)
        if result.scheme in ('', 'http', 'https') \
                and result.netloc in ('hackerrank.com', 'www.hackerrank.com'):
            m = re.match(r'^/contests/([0-9A-Za-z-]+)/challenges/([0-9A-Za-z-]+)(/problem)?/?$', utils.normpath(result.path))
            if m:
                return cls(contest_slug=m.group(1), challenge_slug=m.group(2))
            m = re.match(r'^/challenges/([0-9A-Za-z-]+)(/problem)?/?$', utils.normpath(result.path))
            if m:
                return cls(contest_slug='master', challenge_slug=m.group(1))
        return None

    def _get_model(self, *, session: Optional[requests.Session] = None) -> Dict[str, Any]:
        """
        :raises SubmissionError:
        """

        session = session or utils.get_default_session()
        # get
        url = 'https://www.hackerrank.com/rest/contests/{}/challenges/{}'.format(self.contest_slug, self.challenge_slug)
        resp = utils.request('GET', url, session=session)
        # parse
        it = json.loads(resp.content.decode())
        logger.debug('json: %s', it)
        if not it['status']:
            logger.error('get model: failed')
            raise SubmissionError
        return it['model']

    def _get_lang_display_mapping(self, *, session: Optional[requests.Session] = None) -> Dict[str, str]:
        session = session or utils.get_default_session()
        # get
        url = 'https://hrcdn.net/hackerrank/assets/codeshell/dist/codeshell-cdffcdf1564c6416e1a2eb207a4521ce.js'  # at "Mon Feb  4 14:51:27 JST 2019"
        resp = utils.request('GET', url, session=session)
        # parse
        s = resp.content.decode()
        l = s.index('lang_display_mapping:{c:"C",')
        l = s.index('{', l)
        r = s.index('}', l) + 1
        s = s[l:r]
        logger.debug('lang_display_mapping (raw): %s', s)  # this is not a json
        lang_display_mapping = {}
        for lang in s[1:-2].split('",'):
            key, value = lang.split(':"')
            lang_display_mapping[key] = value
        logger.debug('lang_display_mapping (parsed): %s', lang_display_mapping)
        return lang_display_mapping

    def get_available_languages(self, *, session: Optional[requests.Session] = None) -> List[Language]:
        session = session or utils.get_default_session()
        info = self._get_model(session=session)
        lang_display_mapping = self._get_lang_display_mapping()
        result = []  # type: List[Language]
        for lang in info['languages']:
            descr = lang_display_mapping.get(lang)
            if descr is None:
                logger.warning('display mapping for language `%s\' not found', lang)
                descr = lang
            result += [Language(lang, descr)]
        return result

    def submit_code(self, code: bytes, language_id: LanguageId, *, filename: Optional[str] = None, session: Optional[requests.Session] = None) -> onlinejudge.type.Submission:
        """
        :raises NotLoggedInError:
        :raises SubmissionError:
        """

        session = session or utils.get_default_session()
        if not self.get_service().is_logged_in(session=session):
            raise NotLoggedInError
        # get
        resp = utils.request('GET', self.get_url(), session=session)
        # parse
        soup = bs4.BeautifulSoup(resp.text, utils.HTML_PARSER)
        csrftoken = soup.find('meta', attrs={'name': 'csrf-token'}).attrs['content']
        # post
        url = 'https://www.hackerrank.com/rest/contests/{}/challenges/{}/submissions'.format(self.contest_slug, self.challenge_slug)
        payload = {'code': code.decode('utf-8'), 'language': str(language_id), 'contest_slug': self.contest_slug}
        logger.debug('payload: %s', payload)
        resp = utils.request('POST', url, session=session, json=payload, headers={'X-CSRF-Token': csrftoken})
        # parse
        it = json.loads(resp.content.decode())
        logger.debug('json: %s', it)
        if not it['status']:
            logger.error('Submit Code: failed')
            raise SubmissionError
        model_id = it['model']['id']
        url = self.get_url().rstrip('/') + '/submissions/code/{}'.format(model_id)
        logger.info('success: result: %s', url)
        return utils.DummySubmission(url, problem=self)


onlinejudge.dispatch.services += [HackerRankService]
onlinejudge.dispatch.problems += [HackerRankProblem]
