"""Unit coverage for shared interactive CLI prompts."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import helpers
from crucible.cli import cache as cache_cli
from crucible.cli import config as config_cli
from crucible.cli import dataset as dataset_cli
from crucible.cli import file as file_cli
from crucible.cli import instrument as instrument_cli
from crucible.cli import project as project_cli
from crucible.cli import sample as sample_cli
from crucible.config import config
from crucible.utils.identifiers import IdentifierNotFoundError


def enable_interactive_stdin(monkeypatch):
    monkeypatch.setattr(helpers, '_interactive_stdin', lambda: True)


def test_required_prompt_retries_and_returns_validated_value(monkeypatch, capsys):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['bad', 'VALID'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))

    def validate(value):
        if value != 'VALID':
            raise ValueError('Try again.')
        return value.lower()

    result = helpers.prompt_required(
        'Value',
        validator=validate,
    )

    assert result == 'valid'
    assert 'Invalid value' in capsys.readouterr().err


def test_optional_prompt_retries_instead_of_discarding_invalid_value(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['invalid', 'user@example.org'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))

    assert helpers.prompt_optional(
        'Email', validator=helpers.validate_email) == 'user@example.org'


def test_optional_prompt_returns_none_for_empty_input(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    assert helpers.prompt_optional('Description') is None


def test_default_is_validated_when_input_is_empty(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    monkeypatch.setattr('builtins.input', lambda prompt: '')

    assert helpers.prompt_optional(
        'Project ID', default='Default-Project', validator=str.lower) == 'default-project'


def test_required_prompt_fails_cleanly_without_interactive_stdin(monkeypatch, capsys):
    monkeypatch.setattr(helpers, '_interactive_stdin', lambda: False)

    with pytest.raises(SystemExit) as raised:
        helpers.prompt_required('Project ID', option='--project-id')

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert 'stdin is not interactive' in error
    assert '--project-id' in error


def test_optional_prompt_does_not_fail_without_interactive_stdin(monkeypatch):
    monkeypatch.setattr(helpers, '_interactive_stdin', lambda: False)

    assert helpers.prompt_optional('Description') is None


def test_invalid_default_fails_cleanly_without_interactive_stdin(monkeypatch, capsys):
    monkeypatch.setattr(helpers, '_interactive_stdin', lambda: False)

    def reject(value):
        raise ValueError('Configured project is invalid.')

    with pytest.raises(SystemExit) as raised:
        helpers.prompt_optional(
            'Project ID',
            default='invalid',
            validator=reject,
            option='--project-id',
        )

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert 'Configured project is invalid.' in error
    assert 'Provide --project-id' in error


def test_secret_prompt_uses_getpass(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    monkeypatch.setattr('getpass.getpass', lambda prompt: 'secret-key')
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('input() exposed the secret'))

    assert helpers.prompt_secret('API Key') == 'secret-key'


def test_choice_prompt_retries_and_normalizes(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['owner', 'EDITOR'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))

    assert helpers.prompt_choice(
        'Role', ('viewer', 'contributor', 'editor', 'admin')) == 'editor'


@pytest.mark.parametrize(('response', 'expected'), [
    ('yes', True),
    ('Y', True),
    ('no', False),
    ('N', False),
    ('', False),
])
def test_confirmation_accepts_expected_responses(monkeypatch, response, expected):
    enable_interactive_stdin(monkeypatch)
    monkeypatch.setattr('builtins.input', lambda prompt: response)

    assert helpers.prompt_confirm('Continue?') is expected


def test_confirmation_retries_after_invalid_response(monkeypatch, capsys):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['maybe', 'yes'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))

    assert helpers.prompt_confirm('Continue?') is True
    assert 'Invalid response' in capsys.readouterr().err


def test_confirmation_fails_cleanly_without_interactive_stdin(monkeypatch, capsys):
    monkeypatch.setattr(helpers, '_interactive_stdin', lambda: False)

    with pytest.raises(SystemExit) as raised:
        helpers.prompt_confirm('Delete?', option='--yes')

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert 'stdin is not interactive' in error
    assert '--yes' in error


def test_cache_clear_cancellation_preserves_dataset(monkeypatch, tmp_path):
    target = tmp_path / 'datasets' / 'dataset-mfid'
    target.mkdir(parents=True)
    monkeypatch.setattr(config, '_data', {**config._data, 'cache_dir': str(tmp_path)})
    confirm = MagicMock(return_value=False)
    monkeypatch.setattr(helpers, 'prompt_confirm', confirm)

    cache_cli._execute_clear(SimpleNamespace(
        dataset='dataset-mfid',
        older_than=None,
        yes=False,
    ))

    assert target.exists()
    confirm.assert_called_once()
    assert confirm.call_args.kwargs['option'] == '--yes'


def test_dataset_delete_yes_bypasses_prompt(monkeypatch):
    client = SimpleNamespace(datasets=SimpleNamespace(delete=MagicMock()))
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(
        helpers,
        'prompt_confirm',
        lambda *args, **kwargs: pytest.fail('confirmation should be bypassed'),
    )

    dataset_cli._execute_delete(SimpleNamespace(
        dataset_id='0td7evvtg5wb90005k1j97ak94',
        yes=True,
        debug=False,
    ))

    client.datasets.delete.assert_called_once_with('0td7evvtg5wb90005k1j97ak94')


def test_file_delete_yes_bypasses_prompt(monkeypatch):
    client = SimpleNamespace(files=SimpleNamespace(delete=MagicMock()))
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(
        helpers,
        'prompt_confirm',
        lambda *args, **kwargs: pytest.fail('confirmation should be bypassed'),
    )

    file_cli._execute_delete(SimpleNamespace(
        file_id='0tf7evvtg5wb90005k1j97ak94',
        yes=True,
    ))

    client.files.delete.assert_called_once_with('0tf7evvtg5wb90005k1j97ak94')


def test_file_delete_cancellation_skips_client(monkeypatch, capsys):
    confirm = MagicMock(return_value=False)
    monkeypatch.setattr(helpers, 'prompt_confirm', confirm)
    monkeypatch.setattr(
        'crucible.client.CrucibleClient',
        lambda: pytest.fail('client should not be created'),
    )

    file_cli._execute_delete(SimpleNamespace(
        file_id='0tf7evvtg5wb90005k1j97ak94',
        yes=False,
    ))

    assert capsys.readouterr().out == 'Aborted.\n'
    confirm.assert_called_once_with(
        'Delete file 0tf7evvtg5wb90005k1j97ak94? This cannot be undone.',
        option='--yes',
    )


def test_config_init_cancellation_stops_before_secret_prompt(monkeypatch, tmp_path):
    config_file = tmp_path / 'config.ini'
    config_file.touch()
    monkeypatch.setattr(
        type(config),
        'config_file_path',
        property(lambda self: config_file),
    )
    monkeypatch.setattr(helpers, 'prompt_confirm', lambda message: False)
    monkeypatch.setattr(
        helpers,
        'prompt_secret',
        lambda *args, **kwargs: pytest.fail('secret prompt should not run'),
    )

    config_cli.cmd_init(SimpleNamespace())


def test_project_create_reprompts_for_invalid_required_values(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['-bad', 'valid-project', '', 'LBNL', 'x', 'alice', '', ''])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    client = SimpleNamespace(projects=SimpleNamespace())
    client.projects.create = MagicMock(return_value={
        'unique_id': '0tkn2knjast3h0008nyq9zps2c',
        'project_id': 'valid-project',
        'organization': 'LBNL',
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(project_cli, '_show_project', lambda project: None)

    project_cli._execute_create(SimpleNamespace(
        project_id=None,
        organization=None,
        project_lead=None,
        title=None,
        status=None,
        metadata=None,
        debug=False,
    ))

    project = client.projects.create.call_args.args[0]
    assert project.project_id == 'valid-project'
    assert project.organization == 'LBNL'
    assert project.project_lead == 'alice'


def test_instrument_create_reprompts_for_invalid_slug(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['-bad', 'valid-instrument', '', '', '', ''])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    client = SimpleNamespace(instruments=SimpleNamespace())
    client.instruments.create = MagicMock(return_value={
        'unique_id': '0tkn2knjast3h0008nyq9zps2c',
        'instrument_id': 'valid-instrument',
        'instrument_name': 'Instrument',
        'location': 'Building 67',
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(instrument_cli, '_show_instrument', lambda instrument: None)

    instrument_cli._execute_create(SimpleNamespace(
        instrument_name='Instrument',
        instrument_id=None,
        owner=None,
        location='Building 67',
        manufacturer=None,
        model=None,
        instrument_type=None,
        description=None,
        metadata=None,
        debug=False,
    ))

    instrument = client.instruments.create.call_args.args[0]
    assert instrument.instrument_id == 'valid-instrument'


def test_sample_create_reprompts_when_project_is_not_found(monkeypatch):
    enable_interactive_stdin(monkeypatch)
    answers = iter(['missing-project', 'valid-project', '', '', ''])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    monkeypatch.setattr(config, '_data', {**config._data, 'current_project': None})
    client = SimpleNamespace(projects=SimpleNamespace(), samples=SimpleNamespace())
    client.projects.get = MagicMock(side_effect=[
        IdentifierNotFoundError('Project not found: missing-project'),
        {'unique_id': '0tkn2knjast3h0008nyq9zps2c', 'project_id': 'valid-project'},
    ])
    client.samples.create = MagicMock(return_value={
        'unique_id': '0td7evvtg5wb90005k1j97ak94',
        'sample_name': 'Sample',
        'project_id': 'valid-project',
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(sample_cli, '_show_sample', lambda sample, client: None)

    sample_cli._execute_create(SimpleNamespace(
        name='Sample',
        project_id=None,
        project_mfid=None,
        description=None,
        sample_type=None,
        timestamp=None,
        metadata=None,
        public=False,
        debug=False,
    ))

    sample = client.samples.create.call_args.args[0]
    assert sample.project_id == 'valid-project'
    assert client.projects.get.call_count == 2


def test_sample_create_uses_active_shell_project_without_prompt(monkeypatch):
    monkeypatch.setattr(
        'builtins.input',
        lambda prompt: pytest.fail(f'Unexpected prompt: {prompt}'),
    )
    client = SimpleNamespace(projects=SimpleNamespace(), samples=SimpleNamespace())
    client.projects.get = MagicMock(return_value={
        'unique_id': '0tkn2knjast3h0008nyq9zps2c',
        'project_id': 'shell-project',
    })
    client.samples.create = MagicMock(return_value={
        'unique_id': '0td7evvtg5wb90005k1j97ak94',
        'sample_name': 'Sample',
        'project_id': 'shell-project',
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)
    monkeypatch.setattr(sample_cli, '_show_sample', lambda sample, client: None)

    sample_cli._execute_create(SimpleNamespace(
        name='Sample',
        project_id=None,
        project_mfid=None,
        description=None,
        sample_type=None,
        timestamp=None,
        metadata=None,
        public=False,
        debug=False,
        _shell_state={
            'project': 'shell-project',
            'project_source': 'config file',
        },
    ))

    sample = client.samples.create.call_args.args[0]
    assert sample.project_id == 'shell-project'
