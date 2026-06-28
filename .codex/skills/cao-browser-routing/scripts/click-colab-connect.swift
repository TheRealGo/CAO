#!/usr/bin/env swift
import AppKit
import CoreGraphics
import Foundation

let args = Array(CommandLine.arguments.dropFirst())
guard !args.isEmpty else {
    fputs("usage: click-colab-connect.swift <owner-substring> [x_fraction y_fraction]\n", stderr)
    exit(2)
}

let ownerNeedle = args[0]
let xFraction = args.count >= 2 ? (Double(args[1]) ?? 0.64) : 0.64
let yFraction = args.count >= 3 ? (Double(args[2]) ?? 0.63) : 0.63

let windows = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []

for window in windows {
    let owner = window[kCGWindowOwnerName as String] as? String ?? ""
    let name = window[kCGWindowName as String] as? String ?? ""
    guard owner.contains(ownerNeedle),
          name.localizedCaseInsensitiveContains("Colab") || name.localizedCaseInsensitiveContains("scratchpad") else {
        continue
    }
    guard let bounds = window[kCGWindowBounds as String] as? [String: Any],
          let x = bounds["X"] as? CGFloat,
          let y = bounds["Y"] as? CGFloat,
          let width = bounds["Width"] as? CGFloat,
          let height = bounds["Height"] as? CGFloat else {
        continue
    }

    let appBundle = owner.contains("Atlas") ? "com.openai.atlas" : "com.google.Chrome"
    if let app = NSRunningApplication.runningApplications(withBundleIdentifier: appBundle).first {
        app.activate(options: [.activateAllWindows])
    }
    usleep(300_000)

    let point = CGPoint(x: x + width * CGFloat(xFraction), y: y + height * CGFloat(yFraction))
    CGWarpMouseCursorPosition(point)
    CGAssociateMouseAndMouseCursorPosition(boolean_t(1))
    usleep(100_000)

    let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)
    let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
    down?.post(tap: .cghidEventTap)
    usleep(100_000)
    up?.post(tap: .cghidEventTap)
    print("clicked owner=\(owner) window=\(name) x=\(Int(point.x)) y=\(Int(point.y))")
    exit(0)
}

print("not_found owner_substring=\(ownerNeedle)")
exit(1)
