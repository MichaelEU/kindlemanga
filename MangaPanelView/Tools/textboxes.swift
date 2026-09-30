// Finds lines of text on page images with Apple's Vision framework (on-device).
//
//   textboxes page1.jpg page2.webp ...
//
// Prints JSON to stdout: {"<path>": [[x, y, width, height, confidence, "text"], ...], ...}
// Boxes are in image pixels with the origin at the top left. Used by panelview.py for
// bubble zoom, which only needs where the text is, not what it says.

import Foundation
import ImageIO
import Vision

var result: [String: [[Any]]] = [:]

for path in CommandLine.arguments.dropFirst() {
    guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        result[path] = []
        continue
    }
    let width = Double(image.width), height = Double(image.height)

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    try? VNImageRequestHandler(cgImage: image).perform([request])

    result[path] = (request.results ?? []).compactMap { observation in
        guard let best = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox   // normalised, origin at the bottom left
        return [box.minX * width, (1 - box.maxY) * height, box.width * width, box.height * height,
                Double(best.confidence), best.string]
    }
}

FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result))
