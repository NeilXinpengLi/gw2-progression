from gw2_progression.ontology.execution_os import (
    AISuggestionPlugin,
    CommerceLineagePlugin,
    KernelActionProposal,
    KernelMutationGuard,
    KernelMutationPolicy,
    KernelPluginRole,
    OntologyExecutionOS,
    RuleValidationPlugin,
)
from gw2_progression.ontology.runtime_kernel import OntologyKernel


def test_ai_plugin_can_only_propose_and_kernel_executes(tmp_path, monkeypatch):
    from gw2_progression import database

    monkeypatch.setattr(database, "_TEST_DB_URL", str(tmp_path / "execution-os.db"))
    os = OntologyExecutionOS(kernel=OntologyKernel(tenant_id="execution-os-ai"))
    plugin = AISuggestionPlugin()

    proposal_report = os.propose(plugin, {"decision": "SELL_ITEM", "confidence": 0.8, "reason": "market"})
    result = os.execute_plugin(plugin, {"decision": "SELL_ITEM", "confidence": 0.8, "reason": "market"})

    assert proposal_report["status"] == "accepted"
    assert result["single_execution_truth"] is True
    assert result["executed_count"] == 1
    assert result["rejected_count"] == 0
    assert result["lineage_count"] == 1
    assert result["executions"][0]["kernel"] == "OntologyKernel"


def test_mutation_guard_rejects_plugin_state_mutation_attempt():
    proposal = KernelActionProposal(
        plugin_id="bad:plugin",
        role=KernelPluginRole.AI_SUGGESTION,
        action={"type": "record_decision", "decision": {"decision": "MUTATE", "score": 1, "source": "bad"}},
        evidence={"state": {"entities": {}}},
        mutation_policy=KernelMutationPolicy.PROPOSE_ONLY,
    )

    validation = KernelMutationGuard().validate_proposal(proposal)

    assert validation["valid"] is False
    assert "plugin:evidence_must_not_include_mutating_key:state" in validation["errors"]


def test_rule_and_commerce_plugins_record_lineage_through_kernel(tmp_path, monkeypatch):
    from gw2_progression import database

    monkeypatch.setattr(database, "_TEST_DB_URL", str(tmp_path / "execution-os-lineage.db"))
    os = OntologyExecutionOS(kernel=OntologyKernel(tenant_id="execution-os-lineage"))
    rule = RuleValidationPlugin()
    commerce = CommerceLineagePlugin()

    result = os.execute_proposals([
        *rule.propose({"valid": True, "warnings": []}),
        *commerce.propose({"event_type": "ORDER_FULFILLED", "order_id": "42", "idempotency_key": "idem-1"}),
    ])

    assert result["executed_count"] == 2
    assert result["lineage_count"] == 2
    assert os.kernel.replay_persisted()["deterministic"] is True
