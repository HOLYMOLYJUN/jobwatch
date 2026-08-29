"""조건 매칭 테스트.

watchlist.yml 은 이 프로젝트에서 가장 자주 손대는 파일이다.
규칙 해석이 예상과 다르면 알림이 조용히 어긋나므로, 의미를 테스트로 고정한다.
"""

from __future__ import annotations

import pytest

from jobwatch.matching import Watch, load_watchlist, match_all
from jobwatch.sources.base import JobPost


def post(**kw) -> JobPost:
    base = {
        "id": 1, "source": "jumpit", "title": "백엔드 개발자", "company": "테스트사",
        "url": "https://example.com/1", "tech_stacks": ["Python", "Django"],
        "locations": ["서울 강남구"], "job_category": "서버/백엔드 개발자",
        "min_career": 3, "max_career": 10, "newcomer": False,
    }
    base.update(kw)
    return JobPost(**base)


def test_any_of_matches_title():
    assert Watch(name="w", any_of=["백엔드"]).matches(post())


def test_any_of_matches_tech_stack_not_only_title():
    """제목엔 없고 기술스택에만 있는 경우도 잡아야 한다.

    'QA 엔지니어' 인데 스택에 Playwright 가 있는 공고가 실제로 많다.
    제목만 보면 이런 걸 다 놓친다.
    """
    p = post(title="QA 엔지니어", tech_stacks=["Selenium", "Playwright"])
    assert Watch(name="w", any_of=["Playwright"]).matches(p)


def test_matching_is_case_insensitive():
    assert Watch(name="w", any_of=["playwright"]).matches(post(tech_stacks=["Playwright"]))


def test_none_of_wins_over_any_of():
    """제외 의도가 포함 의도보다 강하다."""
    p = post(title="백엔드 개발자 인턴")
    w = Watch(name="w", any_of=["백엔드"], none_of=["인턴"])
    assert not w.matches(p)


def test_all_of_requires_every_keyword():
    p = post(title="백엔드 개발자", tech_stacks=["Python"])
    assert Watch(name="w", all_of=["백엔드", "Python"]).matches(p)
    assert not Watch(name="w", all_of=["백엔드", "Rust"]).matches(p)


def test_location_partial_match():
    p = post(locations=["부산 해운대구"])
    assert Watch(name="w", locations=["부산"]).matches(p)
    assert not Watch(name="w", locations=["서울"]).matches(p)


@pytest.mark.parametrize(
    "job_min,limit,expected",
    [(0, 3, True), (3, 3, True), (5, 3, False), (None, 3, True)],
)
def test_max_career_means_i_can_apply(job_min, limit, expected):
    """max_career: 3 = '요구 경력 3년 이하인 공고'.

    경력 정보가 없는 공고(None)는 거르지 않는다.
    정보 부족으로 놓치는 것보다 한 번 더 보는 편이 낫다.
    """
    assert Watch(name="w", max_career=limit).matches(post(min_career=job_min)) is expected


def test_min_career_filters_to_senior():
    assert Watch(name="w", min_career=5).matches(post(min_career=7))
    assert not Watch(name="w", min_career=5).matches(post(min_career=2))


def test_newcomer_only():
    assert Watch(name="w", newcomer=True).matches(post(newcomer=True))
    assert not Watch(name="w", newcomer=True).matches(post(newcomer=False))


def test_empty_watch_matches_everything():
    """조건이 하나도 없으면 전부 통과한다 (실수로 빈 조건을 두면 알림 폭탄)."""
    assert Watch(name="w").matches(post())


def test_match_all_returns_only_matched_with_names():
    posts = [post(id=1, title="백엔드"), post(id=2, title="디자이너", job_category="디자인",
                                            tech_stacks=["Figma"])]
    watches = [Watch(name="백엔드", any_of=["백엔드"]), Watch(name="파이썬", any_of=["Python"])]
    result = match_all(posts, watches)
    assert set(result) == {1}
    assert set(result[1]) == {"백엔드", "파이썬"}


def test_load_watchlist(tmp_path):
    p = tmp_path / "w.yml"
    p.write_text(
        "watches:\n  - name: 자동화\n    any_of: [자동화, Playwright]\n    none_of: [인턴]\n",
        encoding="utf-8",
    )
    watches = load_watchlist(p)
    assert len(watches) == 1
    assert watches[0].name == "자동화"
    assert watches[0].none_of == ["인턴"]


def test_load_watchlist_rejects_empty(tmp_path):
    p = tmp_path / "w.yml"
    p.write_text("watches: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_watchlist(p)


def test_none_of_searches_all_fields_even_when_search_in_is_narrow():
    """제외는 search_in 범위에 갇히면 안 된다.

    회귀: search_in: [스택] 조건이 제목의 'PM' 을 못 걸러서
    '개발 PM 채용' 공고가 스택만 맞다는 이유로 알림에 올라왔다.
    """
    p = post(title="개발 PM 채용", tech_stacks=["Next.js", "React"])
    w = Watch(name="스택", search_in=["스택"], any_of=["Next.js"], none_of=["PM"])
    assert not w.matches(p)


def test_search_in_narrows_include_condition():
    """포함 조건은 지정한 필드에서만 찾는다."""
    p = post(title="영상처리 개발자", job_category="프론트엔드 개발자", tech_stacks=["OpenCV"])
    assert Watch(name="w", search_in=["제목"], any_of=["프론트"]).matches(p) is False
    assert Watch(name="w", search_in=["카테고리"], any_of=["프론트"]).matches(p) is True


def test_explain_shows_field_and_keyword():
    p = post(title="프론트엔드 개발자", tech_stacks=["Next.js"])
    w = Watch(name="w", any_of=["프론트엔드", "Next.js"])
    hits = w.explain(p)
    assert "제목:프론트엔드" in hits
    assert "스택:Next.js" in hits
