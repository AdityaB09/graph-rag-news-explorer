#include "engine.hpp"
#include <queue>

void Engine::upsert_nodes(const std::vector<NodeRec>& ns) {
    for (auto& n : ns) nodes_[n.id] = n;
}

void Engine::upsert_edges(const std::vector<EdgeRec>& es) {
    size_t base = edges_.size();
    edges_.insert(edges_.end(), es.begin(), es.end());
    for (size_t i = 0; i < es.size(); ++i) {
        adj_[es[i].src].push_back(base + i);
        adj_[es[i].dst].push_back(base + i);
    }
}

void Engine::expand(const std::vector<std::string>& seeds, int64_t s, int64_t e, uint32_t hops,
                    std::vector<NodeRec>& on, std::vector<EdgeRec>& oe) const {
    std::unordered_set<std::string> seen;
    std::queue<std::pair<std::string,uint32_t>> q;
    for (auto& id : seeds) { q.push({id, 0}); seen.insert(id); }
    while (!q.empty()) {
        auto [u, d] = q.front(); q.pop();
        auto it = nodes_.find(u);
        if (it != nodes_.end()) on.push_back(it->second);
        if (d >= hops) continue;
        auto ait = adj_.find(u);
        if (ait == adj_.end()) continue;
        for (auto ei : ait->second) {
            const auto& ed = edges_[ei];
            if (ed.ts < s || ed.ts > e) continue;
            oe.push_back(ed);
            std::string v = (ed.src == u ? ed.dst : ed.src);
            if (!seen.count(v)) { seen.insert(v); q.push({v, d+1}); }
        }
    }
}
