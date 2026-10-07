import AppKit
let target = CommandLine.arguments[1]
try FileManager.default.createDirectory(atPath: target, withIntermediateDirectories: true)
for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = size * scale
        let image = NSImage(size: NSSize(width: pixels, height: pixels))
        image.lockFocus()
        let factor = CGFloat(pixels) / 1024
        let transform = NSAffineTransform(); transform.scale(by: factor); transform.concat()
        let tile = NSBezierPath(roundedRect: NSRect(x: 60, y: 60, width: 904, height: 904), xRadius: 190, yRadius: 190)
        NSGradient(starting: NSColor(calibratedRed: 0.18, green: 0.38, blue: 0.70, alpha: 1), ending: NSColor(calibratedRed: 0.06, green: 0.13, blue: 0.27, alpha: 1))!.draw(in: tile, angle: -45)
        NSColor.white.setStroke()
        let bubble = NSBezierPath(roundedRect: NSRect(x: 225, y: 370, width: 520, height: 390), xRadius: 95, yRadius: 95)
        bubble.lineWidth = 40; bubble.stroke()
        let tail = NSBezierPath(); tail.move(to: NSPoint(x: 290, y: 370)); tail.line(to: NSPoint(x: 290, y: 285)); tail.line(to: NSPoint(x: 400, y: 370)); tail.lineWidth = 40; tail.stroke()
        NSColor.white.setFill()
        for x in [330, 430] { NSBezierPath(ovalIn: NSRect(x: x, y: 555, width: 40, height: 40)).fill() }
        NSColor(calibratedRed: 0.12, green: 0.25, blue: 0.45, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 540, y: 220, width: 290, height: 350), xRadius: 55, yRadius: 55).fill()
        NSColor.white.setStroke()
        let shackle = NSBezierPath(roundedRect: NSRect(x: 615, y: 365, width: 135, height: 150), xRadius: 65, yRadius: 65); shackle.lineWidth = 35; shackle.stroke()
        NSColor.white.setFill()
        NSBezierPath(roundedRect: NSRect(x: 580, y: 255, width: 205, height: 145), xRadius: 30, yRadius: 30).fill()
        image.unlockFocus()
        let bitmap = NSBitmapImageRep(data: image.tiffRepresentation!)!
        let suffix = scale == 2 ? "@2x" : ""
        try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: target + "/icon_\(size)x\(size)\(suffix).png"))
    }
}
