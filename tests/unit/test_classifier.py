from personal_agent_os.services.project_classifier import classify_project, get_registry


def test_load_registry_returns_list():
    registry = get_registry()
    assert isinstance(registry, list)
    assert len(registry) > 0
    assert "id" in registry[0]
    assert "name" in registry[0]


def test_classify_fitness_content():
    project = classify_project("Just finished my morning workout and feeling great")
    assert project == "answer-movement"


def test_classify_pe_content():
    project = classify_project("Working on an LBO model for a new deal")
    assert project == "pe-prep"


def test_classify_ascend_content():
    project = classify_project("Need to check Canvas for my deadline tomorrow")
    assert project == "ascend"


def test_classify_returns_none_for_ambiguous():
    project = classify_project("the weather is nice today xyz123")
    assert project is None
