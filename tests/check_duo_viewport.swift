import AppKit
import Foundation

// Checks the actual device screenshot, independent of SDL's reported window size.
// A portrait-sized Metal view on the Duo leaves the right edge entirely black.
guard CommandLine.arguments.count == 2,
      let data = try? Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])),
      let image = NSBitmapImageRep(data: data) else {
    fputs("usage: swift tests/check_duo_viewport.swift screenshot.png\n", stderr)
    exit(2)
}

var sampled = 0
var visible = 0
for y in stride(from: image.pixelsHigh * 15 / 100, to: image.pixelsHigh * 85 / 100, by: 21) {
    for x in stride(from: image.pixelsWide * 85 / 100, to: image.pixelsWide * 98 / 100, by: 21) {
        guard let color = image.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { continue }
        sampled += 1
        if max(color.redComponent, color.greenComponent, color.blueComponent) > 0.05 {
            visible += 1
        }
    }
}

let fraction = sampled == 0 ? 0 : Double(visible) / Double(sampled)
print(String(format: "Right-edge visible pixels: %.1f%% (%d/%d)", fraction * 100, visible, sampled))
guard fraction > 0.05 else {
    fputs("FAIL: game viewport does not reach the Duo inner display's right edge\n", stderr)
    exit(1)
}
