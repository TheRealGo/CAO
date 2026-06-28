#!/usr/bin/env swift
import CoreGraphics

let windows = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []

for window in windows {
    let owner = window[kCGWindowOwnerName as String] as? String ?? ""
    let name = window[kCGWindowName as String] as? String ?? ""
    guard owner.contains("Chrome") || owner.contains("Atlas") || name.localizedCaseInsensitiveContains("Colab") || name.localizedCaseInsensitiveContains("scratchpad") else {
        continue
    }
    let bounds = window[kCGWindowBounds as String] ?? [:]
    print("owner=\(owner) name=\(name) bounds=\(bounds)")
}
