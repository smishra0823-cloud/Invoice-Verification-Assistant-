// Local OCR with Apple's Vision framework. No network requests or API key.
import Foundation
import Vision

guard CommandLine.arguments.count == 2 else {
    fputs("Usage: invoice-ocr image.png\n", stderr)
    exit(1)
}

do {
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    try VNImageRequestHandler(url: url, options: [:]).perform([request])
    let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let text = observation.topCandidates(1).first?.string else { return nil }
        return ["text": text, "x": observation.boundingBox.minX,
                "y": observation.boundingBox.midY]
    }
    let data = try JSONSerialization.data(withJSONObject: rows)
    print(String(data: data, encoding: .utf8)!)
} catch {
    fputs("OCR failed: \(error.localizedDescription)\n", stderr)
    exit(1)
}
