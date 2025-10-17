#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "html_parser.hpp"

namespace py = pybind11;

PYBIND11_MODULE(htmlfast, m) {
    py::class_<ParsedHtml>(m, "ParsedHtml")
        .def_readonly("title", &ParsedHtml::title)
        .def_readonly("meta", &ParsedHtml::meta)
        .def_readonly("canonical", &ParsedHtml::canonical)
        .def_readonly("links", &ParsedHtml::links)
        .def_readonly("text", &ParsedHtml::text);
    m.def("parse_html", &parse_html_gumbo, py::arg("html"), py::arg("base_url") = "");
}
