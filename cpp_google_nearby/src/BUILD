load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "nearby_discoverer",
    srcs = ["main.cc"],
    copts = ["-std=c++17"],
    deps = [
        "//connections:core",
    ],
)
