#include "engine.hpp"
#include "graph_engine.grpc.pb.h"
#include <grpcpp/grpcpp.h>
#include <memory>
#include <iostream>

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using graph::GraphEngine;
using graph::Ack;

class GraphServiceImpl final : public GraphEngine::Service {
public:
    Status UpsertNodes(ServerContext*, const graph::UpsertNodesRequest* req, Ack* ack) override {
        std::vector<NodeRec> ns; ns.reserve(req->nodes_size());
        for (const auto& n : req->nodes()) {
            NodeRec r; r.id=n.id(); r.ts=n.ts(); r.type=n.type();
            for (const auto& kv : n.attrs()) r.attrs[kv.first]=kv.second;
            ns.push_back(std::move(r));
        }
        eng_.upsert_nodes(ns); ack->set_ok(true); return Status::OK;
    }
    Status UpsertEdges(ServerContext*, const graph::UpsertEdgesRequest* req, Ack* ack) override {
        std::vector<EdgeRec> es; es.reserve(req->edges_size());
        for (const auto& e : req->edges()) {
            EdgeRec r; r.src=e.src(); r.dst=e.dst(); r.weight=e.weight(); r.ts=e.ts(); r.type=e.type();
            for (const auto& kv : e.attrs()) r.attrs[kv.first]=kv.second;
            es.push_back(std::move(r));
        }
        eng_.upsert_edges(es); ack->set_ok(true); return Status::OK;
    }
    Status ExpandTimeWindow(ServerContext*, const graph::ExpandRequest* req, graph::GraphFragment* out) override {
        std::vector<std::string> seeds(req->seed_ids().begin(), req->seed_ids().end());
        std::vector<NodeRec> ns; std::vector<EdgeRec> es;
        eng_.expand(seeds, req->window().start_ms(), req->window().end_ms(), req->max_hops(), ns, es);
        for (auto& n : ns) {
            auto* nn = out->add_nodes(); nn->set_id(n.id); nn->set_ts(n.ts); nn->set_type(n.type);
            for (auto& kv : n.attrs) (*nn->mutable_attrs())[kv.first]=kv.second;
        }
        for (auto& e : es) {
            auto* ee = out->add_edges(); ee->set_src(e.src); ee->set_dst(e.dst);
            ee->set_weight(e.weight); ee->set_ts(e.ts); ee->set_type(e.type);
            for (auto& kv : e.attrs) (*ee->mutable_attrs())[kv.first]=kv.second;
        }
        return Status::OK;
    }
private:
    Engine eng_;
};

int main() {
    std::string addr("0.0.0.0:50061");
    ServerBuilder b; b.AddListeningPort(addr, grpc::InsecureServerCredentials());
    GraphServiceImpl svc; b.RegisterService(&svc);
    std::unique_ptr<Server> server(b.BuildAndStart());
    std::cout << "GraphEngine listening on " << addr << std::endl;
    server->Wait();
    return 0;
}
