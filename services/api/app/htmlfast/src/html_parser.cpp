#include "html_parser.hpp"
#include <gumbo.h>
#include <algorithm>
#include <cctype>

static std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c){return std::tolower(c);});
    return s;
}

static void extract_text(GumboNode* node, std::string& out) {
    if (!node) return;
    if (node->type == GUMBO_NODE_TEXT) {
        out.append(node->v.text.text);
        out.push_back(' ');
        return;
    }
    if (node->type == GUMBO_NODE_ELEMENT &&
        (node->v.element.tag == GUMBO_TAG_SCRIPT || node->v.element.tag == GUMBO_TAG_STYLE)) {
        return;
    }
    if (node->type == GUMBO_NODE_ELEMENT) {
        GumboVector* children = &node->v.element.children;
        for (unsigned i = 0; i < children->length; ++i)
            extract_text(static_cast<GumboNode*>(children->data[i]), out);
    }
}

static void walk(GumboNode* node, ParsedHtml& out) {
    if (!node || node->type != GUMBO_NODE_ELEMENT) return;
    GumboTag tag = node->v.element.tag;

    if (tag == GUMBO_TAG_TITLE) {
        if (node->v.element.children.length > 0) {
            GumboNode* text = static_cast<GumboNode*>(node->v.element.children.data[0]);
            if (text && text->type == GUMBO_NODE_TEXT) out.title = text->v.text.text;
        }
    }
    if (tag == GUMBO_TAG_META) {
        GumboAttribute* n = gumbo_get_attribute(&node->v.element.attributes, "name");
        GumboAttribute* p = gumbo_get_attribute(&node->v.element.attributes, "property");
        GumboAttribute* c = gumbo_get_attribute(&node->v.element.attributes, "content");
        if (c) {
            if (n) out.meta[to_lower(n->value)] = c->value;
            if (p) out.meta[to_lower(p->value)] = c->value;
        }
    }
    if (tag == GUMBO_TAG_LINK) {
        GumboAttribute* rel = gumbo_get_attribute(&node->v.element.attributes, "rel");
        GumboAttribute* href = gumbo_get_attribute(&node->v.element.attributes, "href");
        if (rel && href) {
            std::string relv = to_lower(rel->value);
            if (relv.find("canonical") != std::string::npos) out.canonical = href->value;
        }
    }
    if (tag == GUMBO_TAG_A) {
        GumboAttribute* href = gumbo_get_attribute(&node->v.element.attributes, "href");
        if (href && href->value && href->value[0] != '\0')
            out.links.emplace_back(href->value);
    }
    GumboVector* children = &node->v.element.children;
    for (unsigned i = 0; i < children->length; ++i)
        walk(static_cast<GumboNode*>(children->data[i]), out);
}

ParsedHtml parse_html_gumbo(const std::string& html, const std::string& /*base_url*/) {
    ParsedHtml out;
    GumboOutput* dom = gumbo_parse(html.c_str());
    walk(dom->root, out);
    std::string text;
    extract_text(dom->root, text);

    std::string sq;
    sq.reserve(text.size());
    bool ws = false;
    for (char ch : text) {
        if (std::isspace(static_cast<unsigned char>(ch))) {
            if (!ws) { sq.push_back(' '); ws = true; }
        } else { sq.push_back(ch); ws = false; }
    }
    std::sort(out.links.begin(), out.links.end());
    out.links.erase(std::unique(out.links.begin(), out.links.end()), out.links.end());
    out.text = sq;
    gumbo_destroy_output(&kGumboDefaultOptions, dom);
    return out;
}
