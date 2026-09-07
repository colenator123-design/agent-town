import AppKit
import Foundation
import Vision

guard CommandLine.arguments.count == 3 else {
    fputs("usage: vision-helper <ocr|classify|codes> <image>\n", stderr)
    exit(2)
}

let mode = CommandLine.arguments[1]
let imageURL = URL(fileURLWithPath: CommandLine.arguments[2])
guard let image = NSImage(contentsOf: imageURL) else {
    fputs("cannot open image\n", stderr)
    exit(3)
}
var proposedRect = CGRect(origin: .zero, size: image.size)
guard let cgImage = image.cgImage(forProposedRect: &proposedRect, context: nil, hints: nil) else {
    fputs("cannot decode image\n", stderr)
    exit(4)
}

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])

do {
    switch mode {
    case "ocr":
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        request.recognitionLanguages = ["zh-Hant", "en-US"]
        try handler.perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        print(lines.joined(separator: "\n"))
    case "classify":
        let request = VNClassifyImageRequest()
        try handler.perform([request])
        for item in (request.results ?? []).filter({ $0.confidence >= 0.08 }).prefix(8) {
            print("\(item.identifier)\t\(String(format: "%.3f", item.confidence))")
        }
    case "codes":
        let request = VNDetectBarcodesRequest()
        try handler.perform([request])
        for item in request.results ?? [] {
            if let payload = item.payloadStringValue {
                print("\(item.symbology.rawValue)\t\(payload)")
            }
        }
    default:
        fputs("unknown mode\n", stderr)
        exit(2)
    }
} catch {
    fputs("Vision request failed: \(error.localizedDescription)\n", stderr)
    exit(5)
}
