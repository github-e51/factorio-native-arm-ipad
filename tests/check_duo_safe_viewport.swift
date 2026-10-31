import AppKit
import Foundation

// Run on a physical Duo app screenshot. The Metal viewport should leave
// narrow dark margins while keeping the UIKit touch controls on top.
guard CommandLine.arguments.count == 2,
      let data = try? Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])),
      let image = NSBitmapImageRep(data: data) else {
    fputs("usage: swift tests/check_duo_safe_viewport.swift screenshot.png\n", stderr)
    exit(2)
}

func dark(_ x: Int, _ y: Int) -> Bool {
    guard let color = image.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { return false }
    return max(color.redComponent, color.greenComponent, color.blueComponent) < 0.04
}

let width = image.pixelsWide
let height = image.pixelsHigh
let samples: [(String, [(Int, Int)])] = [
    ("left", stride(from: height / 5, to: height * 2 / 5, by: 17).map { (6, $0) }),
    ("right", stride(from: height / 5, to: height * 2 / 5, by: 17).map { (width - 7, $0) }),
    ("bottom", stride(from: width * 3 / 10, to: width * 7 / 10, by: 17).map { ($0, height - 7) })
]

var passed = true
for (edge, points) in samples {
    let count = points.filter { dark($0.0, $0.1) }.count
    let fraction = Double(count) / Double(points.count)
    print(String(format: "%@: %.1f%% dark margin (%d/%d)", edge, fraction * 100, count, points.count))
    if fraction < 0.95 { passed = false }
}
if !passed {
    fputs("FAIL: Factorio still draws to the unsafe display edge\n", stderr)
    exit(1)
}

// Measure away from the home indicator and touch buttons. The inner display is
// 3x; the bottom inset should match the 16-point top inset (48 dark pixels).
for x in [width / 3, width * 2 / 3] {
    var topMargin = 0
    while topMargin < height && dark(x, topMargin) {
        topMargin += 1
    }
    var bottomMargin = 0
    while bottomMargin < height && dark(x, height - 1 - bottomMargin) {
        bottomMargin += 1
    }
    print("margins at x=\(x): top \(topMargin), bottom \(bottomMargin) pixels")
    if bottomMargin < 42 || bottomMargin > 54 || abs(bottomMargin - topMargin) > 3 {
        passed = false
    }
}
if !passed {
    fputs("FAIL: bottom margin does not match the 16-point top target\n", stderr)
    exit(1)
}
