load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "nearby_discoverer",
    srcs = ["main.cc"],
    copts = [
        "-std=c++20",
        "-DGITHUB_BUILD",
    ],
    deps = [
        "//connections:core",
        "//connections/implementation:internal",
        "@com_google_absl//absl/strings",
    ],
)
