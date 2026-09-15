"""Optional actual Transformers/PyTorch smoke, with generated tiny local weights."""

import pytest

from dishmook.backends import BackendError, HuggingFaceBackend, snapshot_fingerprint
from dishmook.runtime_models import ModelConfig, ModelRequest
from dishmook.worker import execute


@pytest.mark.hf
def test_actual_local_huggingface_adapter_without_download(tmp_path):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace

    tokenizer_base = Tokenizer(WordLevel({"[UNK]":0, "[EOS]":1, "hello":2, "world":3}, unk_token="[UNK]"))
    tokenizer_base.pre_tokenizer = Whitespace()
    tokenizer = transformers.PreTrainedTokenizerFast(tokenizer_object=tokenizer_base, unk_token="[UNK]", eos_token="[EOS]")
    tokenizer.chat_template = "{% for message in messages %}{{ message['content'] }} {% endfor %}"
    tokenizer.save_pretrained(tmp_path)
    torch.manual_seed(42)
    model = transformers.GPT2LMHeadModel(transformers.GPT2Config(vocab_size=4, n_positions=64, n_embd=16,
                                                               n_layer=1, n_head=2, bos_token_id=1, eos_token_id=1))
    model.save_pretrained(tmp_path, safe_serialization=True)
    config = ModelConfig(backend="huggingface", model_id="local-generated-test-fixture", revision="0"*40,
                         local_path=str(tmp_path), snapshot_sha256=snapshot_fingerprint(tmp_path))
    request = ModelRequest(messages=[{"role":"user","content":"hello world"}], seed=42,
                           max_input_tokens=16, max_output_tokens=4)
    backend = HuggingFaceBackend(config)
    first = backend.generate(request)
    second = backend.generate(request)
    assert first == second
    assert first.token_unit == "model_tokens"
    assert first.input_tokens == 2
    assert 0 < first.output_tokens <= 4
    assert first.metadata["snapshot_sha256"] == config.snapshot_sha256
    # Also exercise serialization, loading and usage through the real killable worker.
    assert execute(config, request, 30) == first
    request.max_input_tokens = 1
    with pytest.raises(BackendError, match="input_budget_exceeded"):
        backend.generate(request)
    (tmp_path / "changed.txt").write_text("changed")
    with pytest.raises(BackendError, match="model_snapshot_changed"):
        backend.generate(request)
