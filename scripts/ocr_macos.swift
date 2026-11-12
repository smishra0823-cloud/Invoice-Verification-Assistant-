// Local OCR. A page pass plus overlapping strips recover missed small text.
import Foundation
import Vision
import ImageIO

struct ReadLine {
    let text: String
    let box: CGRect
}

func recognize(_ image: CGImage, offset: Double = 0, scale: Double = 1) throws -> [ReadLine] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    return (request.results ?? []).compactMap { observation in
        guard let text = observation.topCandidates(1).first?.string else { return nil }
        let r = observation.boundingBox
        return ReadLine(text: text, box: CGRect(x: r.minX, y: offset + r.minY * scale, width: r.width, height: r.height * scale))
    }
}

guard CommandLine.arguments.count == 2 else { exit(1) }
do {
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { exit(1) }
    var lines = try recognize(image)
    let height = image.height
    for index in 0..<3 {
        let start = max(0, index * height / 3 - height / 30)
        let end = min(height, (index + 1) * height / 3 + height / 30)
        let rect = CGRect(x: 0, y: start, width: image.width, height: end - start)
        guard let strip = image.cropping(to: rect) else { continue }
        let extra = try recognize(strip, offset: Double(height - end) / Double(height), scale: Double(end - start) / Double(height))
        for candidate in extra {
            let overlaps = lines.contains { existing in
                let intersection = existing.box.intersection(candidate.box)
                let smallArea = min(existing.box.width * existing.box.height, candidate.box.width * candidate.box.height)
                return !intersection.isNull && intersection.width * intersection.height > smallArea * 0.35
            }
            // Fill missing regions only; never replace a number using arithmetic.
            if !overlaps { lines.append(candidate) }
        }
    }
    let rows: [[String: Any]] = lines.map { ["text": $0.text, "x": $0.box.minX, "y": $0.box.midY, "height": $0.box.height] }
    let data = try JSONSerialization.data(withJSONObject: rows)
    print(String(data: data, encoding: .utf8)!)
} catch {
    fputs("OCR failed: \(error.localizedDescription)\n", stderr)
    exit(1)
}
