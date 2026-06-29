"""Start the full Cognitive OS pipeline for 10-hour continuous operation."""
import time, os, sys
from datetime import datetime
from gw2_progression.cognitive_os.engine import get_cognitive_os

LOG = "pipeline_output.log"
os.makedirs("logs", exist_ok=True)
logfile = open(f"logs/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", "w", encoding="utf-8")

def log(msg):
    line = f"[{datetime.now().isoformat()}] {msg}"
    print(line, flush=True)
    logfile.write(line + "\n")
    logfile.flush()

cos = get_cognitive_os()
cos.initialize({
    'gold': 5000,
    'inventory': {'mystic_coin': 50, 'mithril_ore': 200, 'ectoplasm': 25},
    'achievements': ['daily_completer', 'world_explorer'],
})
factory = cos.data_factory
log(f'INIT OK. Gold={cos.temporal.current.get("gold", 0)}')

log('=== PHASE 1: DATA INGESTION ===')
results = factory.collect_all()
for r in results:
    log(f'  [{("OK" if r.success else "FAIL")}] {r.source_id}: {r.total_entities} entities')

log('=== PHASE 2: DGSK GRAPH BUILD ===')
gb_result = factory.build_graph()
log(f'  Nodes: {gb_result.total_nodes}, Edges: {gb_result.total_edges}')

log('=== PHASE 3: BEHAVIOR + GNN ===')
behavior = cos.classify_behavior()
log(f'  Dominant: {behavior["dominant_archetype"]}')
gnn = cos.gnn_induction()
log(f'  Rules: {len(gnn["induced_rules"])}')

log('=== PHASE 4: PROBABILISTIC INFERENCE ===')
pstep = cos.probabilistic_step()
dec = pstep["bors_distribution"]["sampled_decision"]
log(f'  Decision: {dec}, Uncertainty: {pstep["target_uncertainty"]:.4f}')
worlds = cos.run_multi_world(num_worlds=5, steps=20)
log(f'  Multi-world: {worlds["world_count"]}, Diversity: {worlds["world_diversity"]:.4f}')

log('=== PHASE 5: CALIBRATION ===')
cal = cos.calibrate(cos.temporal.current)
log(f'  Loss: {cal["loss"]:.4f}, Trend: {cal["calibration_state"]["loss_trend"]}')

log('=== PHASE 6: DATASETS ===')
ds = cos.generate_datasets()
log(f'  Datasets: {ds["datasets_saved"]}, Samples: {ds["total_samples"]}')

log('\n' + '='*60)
log('STARTING CONTINUOUS PIPELINE')
log(f'Target: 10 hours (until {datetime.fromtimestamp(time.time()+36000).isoformat()})')
log('='*60)

factory.start()
start_time = time.time()
end_time = start_time + 36000
iteration = 0

try:
    while time.time() < end_time:
        iteration += 1
        elapsed = (time.time() - start_time) / 3600
        remaining = (end_time - time.time()) / 3600
        log(f'\n--- Iter {iteration} @ {elapsed:.2f}h ({remaining:.1f}h left) ---')

        fw = factory.run_flywheel()
        for i, r in enumerate(fw):
            log(f'  FW[{i}]: ingest={r.sources_ingested}s | graph={r.graph_nodes}N/{r.graph_edges}E | ds={r.dataset_samples}samples')

        pstep = cos.probabilistic_step()
        cal = cos.calibrate(cos.temporal.current)
        dec = pstep["bors_distribution"]["sampled_decision"]
        log(f'  Decision: {dec} | Uncert: {pstep["target_uncertainty"]:.4f} | Loss: {cal["loss"]:.4f} ({cal["calibration_state"]["loss_trend"]}) | Reward: {pstep["reward"]}')

        if iteration % 5 == 0:
            ds = cos.generate_datasets()
            log(f'  [CHECKPOINT] Datasets: {ds["datasets_saved"]}, Samples: {ds["total_samples"]}')

        time.sleep(60)

except KeyboardInterrupt:
    log('\nINTERRUPTED')
except Exception as e:
    log(f'ERROR: {e}')
    import traceback
    log(traceback.format_exc())
finally:
    elapsed = (time.time() - start_time) / 3600
    cos.generate_datasets()
    factory.stop()
    log('\n' + '='*60)
    log(f'DONE: {elapsed:.2f}h, {iteration} iterations')
    log(f'Datasets: {factory.dataset_builder.total_samples()}')
    log(f'Flywheel: {factory.status.total_flywheel_iterations}')
    log(f'Ingestions: {factory.status.total_ingestions}')
    log('='*60)
    logfile.close()
