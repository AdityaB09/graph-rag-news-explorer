#pragma once
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <cstdint>

struct NodeRec {
    std::string id, type;
    int64_t ts = 0;
    std::unordered_map<std::string, std::string> attrs;
};

struct EdgeRec {
    std::string src, dst, type;
    double weight = 1.0;
    int64_t ts = 0;
    std::unordered_map<std::string, std::string> attrs;
};

class Engine {
public:
    void upsert_nodes(const std::vector<NodeRec>& ns);
    void upsert_edges(const std::vector<EdgeRec>& es);
    void expand(const std::vector<std::string>& seeds, int64_t start_ms, int64_t end_ms, uint32_t hops,
                std::vector<NodeRec>& out_nodes, std::vector<EdgeRec>& out_edges) const;
private:
    std::unordered_map<std::string, NodeRec> nodes_;
    std::vector<EdgeRec> edges_;
    std::unordered_map<std::string, std::vector<size_t>> adj_;
};
