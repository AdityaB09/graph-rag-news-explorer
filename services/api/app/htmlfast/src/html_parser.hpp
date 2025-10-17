#pragma once
#include <string>
#include <vector>
#include <unordered_map>

struct ParsedHtml {
    std::string title;
    std::unordered_map<std::string, std::string> meta;
    std::string canonical;
    std::vector<std::string> links;
    std::string text;
};
ParsedHtml parse_html_gumbo(const std::string& html, const std::string& base_url = "");
