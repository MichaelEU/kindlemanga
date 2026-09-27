import SwiftUI
import AppKit
import UniformTypeIdentifiers

// MARK: - App

@main
struct MangaPanelViewApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var converter = Converter()

    var body: some Scene {
        Window("Manga Panel View", id: "main") {
            ContentView()
                .environmentObject(converter)
                .frame(minWidth: 900, idealWidth: 1040, minHeight: 600, idealHeight: 740)
        }
        .windowResizability(.contentMinSize)
        .commands { AppCommands() }

        Window("About Manga Panel View", id: "about") {
            AboutView()
        }
        .windowResizability(.contentSize)
        .defaultPosition(.center)
    }
}

enum Links {
    static let repo = URL(string: "https://github.com/MichaelEU/kindlemanga")!
    static let kumiko = URL(string: "https://github.com/njean42/kumiko")!
    static let kcc = URL(string: "https://github.com/ciromattia/kcc")!
    static let xtcjs = URL(string: "https://github.com/varo6/xtcjs")!
    static let crosspoint = URL(string: "https://github.com/crosspoint-reader/crosspoint-reader")!
    static let opencv = URL(string: "https://opencv.org")!
    static let numpy = URL(string: "https://numpy.org")!
    static let pillow = URL(string: "https://python-pillow.org")!
    static let requests = URL(string: "https://requests.readthedocs.io")!
    static let claudeCode = URL(string: "https://claude.com/claude-code")!
}

struct AppCommands: Commands {
    @Environment(\.openWindow) private var openWindow

    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            Button("About Manga Panel View") { openWindow(id: "about") }
        }
        CommandGroup(replacing: .help) {
            Button("Manga Panel View on GitHub") { NSWorkspace.shared.open(Links.repo) }
            Button("Acknowledgements") { openWindow(id: "about") }
        }
    }
}

/// Handles folders/.cbz files dropped on the Dock icon, and stops work on quit.
final class AppDelegate: NSObject, NSApplicationDelegate {
    static weak var converter: Converter?
    static var pending: [URL] = []

    func application(_ application: NSApplication, open urls: [URL]) {
        if let c = Self.converter { c.add(urls) } else { Self.pending += urls }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        Self.converter?.stop()
    }
}

// MARK: - Model

enum DeviceGroup: CaseIterable {
    case kindle, olderKindle, kobo, sony, other

    var title: String {
        switch self {
        case .kindle: "Kindle: zooms panel by panel"
        case .olderKindle: "Older Kindle: one panel per page"
        case .kobo: "Kobo: one panel per page"
        case .sony: "Sony Reader: one panel per page"
        case .other: "Other readers: one panel per page"
        }
    }
}

/// Raw values are the converter's `-d` device ids. Screen sizes follow Kindle Comic Converter's profiles.
enum Device: String, CaseIterable, Identifiable {
    case basic, k600, kpw, kpw34, kpw5, kpw6, kcs, ko, scribe, ks3, kscs
    case k34, kdx, k12
    case koc, kon, kol, kos, koe
    case prs500, prs300, prs600, prs950, prst, prst3
    case x4, generic

    var id: String { rawValue }

    private var spec: (label: String, group: DeviceGroup, width: Int, height: Int, format: String?) {
        switch self {
        case .basic: ("Kindle (2022 and later)", .kindle, 1072, 1448, nil)
        case .k600: ("Kindle 5, 7, 8 or 10", .kindle, 600, 800, nil)
        case .kpw: ("Kindle Paperwhite 1 or 2", .kindle, 758, 1024, nil)
        case .kpw34: ("Kindle Paperwhite 3 or 4, Voyage, Oasis 1", .kindle, 1072, 1448, nil)
        case .kpw5: ("Kindle Paperwhite 5 or Signature", .kindle, 1236, 1648, nil)
        case .kpw6: ("Kindle Paperwhite 6 (2024)", .kindle, 1272, 1696, nil)
        case .kcs: ("Kindle Colorsoft", .kindle, 1272, 1696, nil)
        case .ko: ("Kindle Oasis 2 or 3", .kindle, 1264, 1680, nil)
        case .scribe: ("Kindle Scribe 1 or 2", .kindle, 1860, 2480, nil)
        case .ks3: ("Kindle Scribe 3", .kindle, 1986, 2648, nil)
        case .kscs: ("Kindle Scribe Colorsoft", .kindle, 1986, 2648, nil)
        case .k34: ("Kindle Keyboard or Touch", .olderKindle, 600, 800, nil)
        case .kdx: ("Kindle DX", .olderKindle, 824, 1000, nil)
        case .k12: ("Kindle 1 or 2", .olderKindle, 600, 670, nil)
        case .koc: ("Kobo Clara", .kobo, 1072, 1448, "CBZ")
        case .kon: ("Kobo Nia", .kobo, 758, 1024, "CBZ")
        case .kol: ("Kobo Libra", .kobo, 1264, 1680, "CBZ")
        case .kos: ("Kobo Sage or Forma", .kobo, 1440, 1920, "CBZ")
        case .koe: ("Kobo Elipsa", .kobo, 1404, 1872, "CBZ")
        case .x4: ("Xteink X4", .other, 480, 800, "XTCH")
        case .prs500: ("Sony PRS-500 or 505", .sony, 600, 800, "PDF")
        case .prs300: ("Sony PRS-300 or 350 (Pocket)", .sony, 600, 800, "PDF")
        case .prs600: ("Sony PRS-600, 650 or 700 (Touch)", .sony, 600, 800, "PDF")
        case .prs950: ("Sony PRS-900 or 950 (Daily Edition)", .sony, 600, 1024, "PDF")
        case .prst: ("Sony PRS-T1 or T2", .sony, 600, 800, "PDF")
        case .prst3: ("Sony PRS-T3", .sony, 758, 1024, "PDF")
        case .generic: ("Other reader (CBZ)", .other, 1264, 1680, "CBZ")
        }
    }

    var label: String { spec.label }
    var group: DeviceGroup { spec.group }

    /// Output folder. Kept stable for devices from earlier versions, so finished chapters are still skipped.
    var folder: String {
        switch self {
        case .basic: "Kindle"
        case .scribe: "Kindle Scribe"
        case .prs950: "Sony PRS-950"
        default: label
        }
    }

    /// Any Kindle: uses the Kindle format setting (EPUB or MOBI).
    var isKindle: Bool { group == .kindle || group == .olderKindle }
    /// Zooms inside the page; everything else gets one panel per page.
    var zooms: Bool { group == .kindle }
    var isColor: Bool { self == .kcs || self == .kscs }

    var symbol: String {
        switch group {
        case .kindle: self == .scribe || self == .ks3 || self == .kscs ? "pencil.and.scribble" : "book.closed"
        case .olderKindle: "book.closed.fill"
        case .kobo: "books.vertical"
        case .sony: "book"
        case .other: self == .x4 ? "rectangle.portrait" : "square.stack"
        }
    }

    var detail: String {
        var parts = [zooms ? "Panel zoom" : "One panel per page"]
        if let format = spec.format { parts.append(format) }
        parts.append("\(spec.width)×\(spec.height)")
        if isColor { parts.append("colour") }
        return parts.joined(separator: " · ")
    }
}

struct Failure: Identifiable {
    let id = UUID()
    let device: Device
    let chapter: String
    let message: String
}

enum ItemState { case waiting, running, stopped, done }

struct QueueItem: Identifiable {
    let id = UUID()
    let url: URL
    var chapterCount: Int?
    var state: ItemState = .waiting
    var converted = 0
    var alreadyDone = 0
    var failures: [Failure] = []
    var currentDevice: Device?
    var deviceIndex = 0
    var deviceCount = 1
    var deviceDone = 0
    var deviceTotal = 0

    var isFile: Bool { url.pathExtension.lowercased() == "cbz" }
    var name: String { isFile ? url.deletingPathExtension().lastPathComponent : url.lastPathComponent }
    var isPending: Bool { state == .waiting || state == .stopped }

    var progress: Double {
        switch state {
        case .done: return 1
        case .running:
            let within = deviceTotal > 0 ? Double(deviceDone) / Double(deviceTotal) : 0
            return (Double(deviceIndex) + within) / Double(max(deviceCount, 1))
        default: return 0
        }
    }
}

enum EngineState: Equatable {
    case checking, needsSetup, installing, ready
    case failed(String)
}

final class Converter: ObservableObject {
    static let kindlegen = "/Applications/Kindle Previewer 4.app/Contents/Resources/KFXGen/bin/kindlegen"
    static let previewerURL = URL(string: "https://www.amazon.com/Kindle-Previewer/b?node=21381691011")!

    let engineDir: URL
    var python: URL { engineDir.appendingPathComponent("venv/bin/python") }
    var script: URL { engineDir.appendingPathComponent("panelview.py") }
    private let defaults = UserDefaults.standard

    // Engine
    @Published var engine: EngineState = .checking
    @Published var setupLog: [String] = []

    // Settings (remembered between launches)
    @Published var output: URL { didSet { defaults.set(output.path, forKey: "output") } }
    @Published var device: Device {
        didSet {
            defaults.set(device.rawValue, forKey: "device")
            recentDevices = Array(([device] + recentDevices.filter { $0 != device }).prefix(3))
        }
    }
    @Published var recentDevices: [Device] { didSet { defaults.set(recentDevices.map(\.rawValue), forKey: "recentDevices") } }
    @Published var rightToLeft: Bool { didSet { defaults.set(rightToLeft, forKey: "rtl") } }
    @Published var skipFirst: Int { didSet { defaults.set(skipFirst, forKey: "skipFirst") } }
    @Published var skipLast: Int { didSet { defaults.set(skipLast, forKey: "skipLast") } }
    @Published var jobs: Int { didSet { defaults.set(jobs, forKey: "jobs") } }
    @Published var format: String { didSet { defaults.set(format, forKey: "format") } }   // Kindle: "epub" or "mobi"
    @Published var pageFirst: Bool { didSet { defaults.set(pageFirst, forKey: "pageFirst") } }
    @Published var rotateWide: Bool { didSet { defaults.set(rotateWide, forKey: "rotateWide") } }
    @Published var xteinkFormat: String { didSet { defaults.set(xteinkFormat, forKey: "xteinkFormat") } }  // "xtch" or "xtc"

    // Queue (unfinished titles are remembered between launches)
    @Published var queue: [QueueItem] = [] { didSet { saveQueue() } }
    @Published var running = false
    @Published var currentItemID: UUID?
    @Published var runCompleted = 0
    private var process: Process?
    private var cancelled = false
    private var unparsed: [String] = []
    private var savedQueue: [String] = []
    private let countQueue = DispatchQueue(label: "chapter-count", qos: .userInitiated)

    init() {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        engineDir = support.appendingPathComponent("Manga Panel View", isDirectory: true)
        let d = UserDefaults.standard
        d.register(defaults: ["useBasic": true, "useScribe": false, "rtl": true,
                              "skipFirst": 1, "skipLast": 1, "jobs": 2, "format": "epub",
                              "pageFirst": false, "rotateWide": false, "xteinkFormat": "xtch"])
        output = d.string(forKey: "output").map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                .appendingPathComponent("Kindle Manga", isDirectory: true)
        // Earlier versions allowed several devices at once ("devices", or the "useBasic"/"useScribe" switches).
        let earlier = (d.stringArray(forKey: "devices") ?? []).compactMap(Device.init(rawValue:))
        let current = d.string(forKey: "device").flatMap(Device.init(rawValue:))
            ?? Device.allCases.first(where: earlier.contains)
            ?? (d.bool(forKey: "useScribe") ? .scribe : .basic)
        device = current
        let recents = (d.stringArray(forKey: "recentDevices") ?? []).compactMap(Device.init(rawValue:))
        recentDevices = Array(([current] + (recents.isEmpty ? earlier : recents).filter { $0 != current }).prefix(3))
        pageFirst = d.bool(forKey: "pageFirst")
        rotateWide = d.bool(forKey: "rotateWide")
        xteinkFormat = d.string(forKey: "xteinkFormat") ?? "xtch"
        rightToLeft = d.bool(forKey: "rtl")
        skipFirst = d.integer(forKey: "skipFirst")
        skipLast = d.integer(forKey: "skipLast")
        jobs = d.integer(forKey: "jobs")
        format = d.string(forKey: "format") ?? "epub"

        let restored = (d.stringArray(forKey: "queue") ?? []).map { URL(fileURLWithPath: $0) }
        AppDelegate.converter = self
        add(restored + AppDelegate.pending)
        AppDelegate.pending = []
    }

    var selectedDevices: [Device] { [device] }
    var anyKindle: Bool { device.isKindle }
    var anyPanels: Bool { !device.zooms }
    var needsKindlegen: Bool { anyKindle && format == "mobi" }

    /// A checkmarked menu item that selects `choice`.
    func selection(_ choice: Device) -> Binding<Bool> {
        Binding(get: { self.device == choice }, set: { _ in self.device = choice })
    }

    var hasKindlegen: Bool { FileManager.default.isExecutableFile(atPath: Self.kindlegen) }
    var pendingCount: Int { queue.filter(\.isPending).count }
    var totalChapters: Int { queue.compactMap(\.chapterCount).reduce(0, +) }
    var currentItem: QueueItem? { currentItemID.flatMap { id in queue.first { $0.id == id } } }

    var canStart: Bool {
        !running && pendingCount > 0 && !selectedDevices.isEmpty && (!needsKindlegen || hasKindlegen)
    }

    /// 0...1 across every title in this run, including titles added while it runs.
    var overallProgress: Double {
        let total = runCompleted + pendingCount + (currentItem == nil ? 0 : 1)
        guard total > 0 else { return 0 }
        return (Double(runCompleted) + (currentItem?.progress ?? 0)) / Double(total)
    }

    // MARK: Queue

    func add(_ urls: [URL]) {
        let fm = FileManager.default
        for url in urls {
            var isDir: ObjCBool = false
            guard fm.fileExists(atPath: url.path, isDirectory: &isDir),
                  isDir.boolValue || url.pathExtension.lowercased() == "cbz" else { continue }
            let std = url.standardizedFileURL
            if queue.contains(where: { $0.url.standardizedFileURL == std && $0.state != .done }) { continue }
            let item = QueueItem(url: std)
            queue.append(item)
            countChapters(item)
        }
    }

    func remove(_ id: UUID) {
        guard id != currentItemID else { return }
        queue.removeAll { $0.id == id }
    }

    func clearFinished() { queue.removeAll { $0.state == .done } }

    func clearAll() {
        guard !running else { return }
        queue.removeAll()
    }

    private func countChapters(_ item: QueueItem) {
        let (id, src) = (item.id, item.url)
        countQueue.async {
            var n = 0
            if src.pathExtension.lowercased() == "cbz" {
                n = 1
            } else if let e = FileManager.default.enumerator(at: src, includingPropertiesForKeys: nil,
                                                             options: [.skipsHiddenFiles]) {
                for case let u as URL in e where u.pathExtension.lowercased() == "cbz" { n += 1 }
            }
            DispatchQueue.main.async { self.update(id) { $0.chapterCount = n } }
        }
    }

    private func update(_ id: UUID, _ change: (inout QueueItem) -> Void) {
        if let i = queue.firstIndex(where: { $0.id == id }) { change(&queue[i]) }
    }

    private func saveQueue() {
        let paths = queue.filter { $0.state != .done }.map(\.url.path)
        if paths != savedQueue {
            savedQueue = paths
            defaults.set(paths, forKey: "queue")
        }
    }

    // MARK: Engine

    func prepareEngine() {
        let fm = FileManager.default
        try? fm.createDirectory(at: engineDir, withIntermediateDirectories: true)
        // Always refresh the bundled scripts so app updates take effect.
        if let res = Bundle.main.resourceURL {
            for name in ["panelview.py", "kumiko"] {
                let dst = engineDir.appendingPathComponent(name)
                try? fm.removeItem(at: dst)
                try? fm.copyItem(at: res.appendingPathComponent(name), to: dst)
            }
        }
        engine = fm.isExecutableFile(atPath: python.path) ? .ready : .needsSetup
    }

    func installEngine() {
        engine = .installing
        setupLog = []
        let venv = engineDir.appendingPathComponent("venv").path
        let cmd = """
        set -e
        PY=$(command -v python3) || { echo "Python 3 was not found. Install it from python.org and try again."; exit 1; }
        echo "Using $PY"
        rm -rf '\(venv)'
        "$PY" -m venv '\(venv)'
        '\(venv)/bin/pip' install --disable-pip-version-check "opencv-python-headless==4.10.0.84" "numpy<2.1" pillow requests
        '\(venv)/bin/python' -c "import cv2, numpy, PIL, requests; print('Engine ready')"
        """
        Task { @MainActor in
            let code = await run("/bin/zsh", ["-lc", cmd]) { line in
                self.setupLog.append(line)
                if self.setupLog.count > 300 { self.setupLog.removeFirst(self.setupLog.count - 300) }
            }
            self.engine = code == 0 ? .ready
                : .failed(self.setupLog.last(where: { !$0.isEmpty }) ?? "Setup failed (exit \(code)).")
        }
    }

    // MARK: Convert

    func start() {
        guard canStart else { return }
        let devices = selectedDevices
        running = true
        cancelled = false
        runCompleted = 0
        Task { @MainActor in
            // Re-checks the queue each time, so titles dropped in mid-run get picked up.
            while !self.cancelled, let next = self.queue.first(where: \.isPending) {
                await self.convert(next.id, devices: devices)
                if !self.cancelled { self.runCompleted += 1 }
            }
            self.currentItemID = nil
            self.process = nil
            self.running = false
        }
    }

    private func convert(_ id: UUID, devices: [Device]) async {
        guard let item = queue.first(where: { $0.id == id }) else { return }
        currentItemID = id
        update(id) {
            $0.state = .running
            $0.converted = 0; $0.alreadyDone = 0; $0.failures = []
            $0.deviceCount = devices.count
        }
        for (index, device) in devices.enumerated() {
            if cancelled { break }
            update(id) {
                $0.deviceIndex = index; $0.currentDevice = device
                $0.deviceDone = 0; $0.deviceTotal = 0
            }
            unparsed = []
            var args = ["-u", script.path, item.url.path,
                        "-d", device.rawValue,
                        "-o", output.appendingPathComponent(device.folder).path,
                        "--skip-first", "\(skipFirst)", "--skip-last", "\(skipLast)",
                        "-j", "\(jobs)"]
            if device.isKindle { args += ["--format", format] }
            if device == .x4 { args += ["--format", xteinkFormat] }
            if !device.zooms {
                if pageFirst { args.append("--page-first") }
                if rotateWide { args.append("--rotate-wide") }
            }
            if !rightToLeft { args.append("--ltr") }
            let code = await run(python.path, args) { self.handle($0, device: device, id: id) }
            if code != 0 && !cancelled {
                let why = unparsed.last(where: { !$0.isEmpty }) ?? "exit code \(code)"
                update(id) { $0.failures.append(Failure(device: device, chapter: "Converter stopped", message: why)) }
            }
        }
        update(id) {
            $0.currentDevice = nil
            $0.state = self.cancelled ? .stopped : .done
        }
        currentItemID = nil
    }

    func stop() {
        cancelled = true
        guard let p = process, p.isRunning else { return }
        kill(-p.processIdentifier, SIGTERM)   // the converter runs in its own process group
        p.terminate()
    }

    func reveal(_ item: QueueItem? = nil) {
        var dirs = selectedDevices.map { output.appendingPathComponent($0.folder) }
        if let item, !item.isFile {
            let series = dirs.map { $0.appendingPathComponent(item.name) }
            if series.contains(where: { FileManager.default.fileExists(atPath: $0.path) }) { dirs = series }
        }
        dirs = dirs.filter { FileManager.default.fileExists(atPath: $0.path) }
        if dirs.isEmpty {
            try? FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
            NSWorkspace.shared.open(output)
        } else {
            NSWorkspace.shared.activateFileViewerSelecting(dirs)
        }
    }

    private func handle(_ line: String, device: Device, id: UUID) {
        if let m = line.firstMatch(of: #/^(\d+) to convert, (\d+) already done/#) {
            update(id) {
                $0.deviceTotal = Int(m.1) ?? 0
                $0.alreadyDone += Int(m.2) ?? 0
            }
        } else if let m = line.firstMatch(of: #/^\[\d+/\d+\] (ok  |FAIL) (.+?)(?:  -> (.*))?$/#) {
            let ok = m.1 == "ok  "
            let chapter = String(m.2).replacingOccurrences(of: ".cbz", with: "")
                .replacingOccurrences(of: "/", with: " · ")
            let message = m.3.map(String.init) ?? ""
            update(id) {
                $0.deviceDone += 1
                if ok { $0.converted += 1 }
                else { $0.failures.append(Failure(device: device, chapter: chapter, message: message)) }
            }
        } else {
            unparsed.append(line)
            if unparsed.count > 50 { unparsed.removeFirst() }
        }
    }

    /// Runs a process, delivering each output line on the main queue.
    private func run(_ exe: String, _ args: [String], onLine: @escaping (String) -> Void) async -> Int32 {
        await withCheckedContinuation { (cont: CheckedContinuation<Int32, Never>) in
            let p = Process()
            p.executableURL = URL(fileURLWithPath: exe)
            p.arguments = args
            var env = ProcessInfo.processInfo.environment
            env["PYTHONUNBUFFERED"] = "1"
            p.environment = env
            let pipe = Pipe()
            p.standardOutput = pipe
            p.standardError = pipe
            DispatchQueue.global(qos: .userInitiated).async {
                do { try p.run() } catch {
                    DispatchQueue.main.async { onLine(error.localizedDescription); cont.resume(returning: -1) }
                    return
                }
                DispatchQueue.main.async { self.process = p }
                let fh = pipe.fileHandleForReading
                var buffer = Data()
                func flush(all: Bool) {
                    while let r = buffer.firstIndex(of: 0x0A) {
                        let line = String(decoding: buffer[buffer.startIndex..<r], as: UTF8.self)
                        buffer.removeSubrange(buffer.startIndex...r)
                        DispatchQueue.main.async { onLine(line) }
                    }
                    if all && !buffer.isEmpty {
                        let line = String(decoding: buffer, as: UTF8.self)
                        buffer.removeAll()
                        DispatchQueue.main.async { onLine(line) }
                    }
                }
                while true {
                    let d = fh.availableData
                    if d.isEmpty { break }
                    buffer.append(d)
                    flush(all: false)
                }
                flush(all: true)
                p.waitUntilExit()
                let status = p.terminationStatus
                DispatchQueue.main.async { cont.resume(returning: status) }
            }
        }
    }
}

// MARK: - Views

struct ContentView: View {
    @EnvironmentObject var c: Converter

    var body: some View {
        Group {
            if c.engine == .ready { MainView() } else { SetupView() }
        }
        .onAppear { c.prepareEngine() }
    }
}

struct SetupView: View {
    @EnvironmentObject var c: Converter

    var body: some View {
        VStack(spacing: 14) {
            Image(nsImage: NSApp.applicationIconImage)
                .resizable().frame(width: 96, height: 96)
            Text("Manga Panel View").font(.title.bold())

            switch c.engine {
            case .checking, .ready:
                ProgressView().controlSize(.small)
            case .needsSetup:
                Text("One-time setup").font(.headline)
                Text("Downloads the panel detector (about 100 MB) into Application Support. Needs Python 3 and an internet connection.")
                    .multilineTextAlignment(.center).foregroundStyle(.secondary)
                Button("Set Up") { c.installEngine() }
                    .buttonStyle(.borderedProminent).controlSize(.large)
            case .installing:
                ProgressView("Setting up…")
                Text(c.setupLog.last ?? " ")
                    .font(.caption.monospaced()).foregroundStyle(.secondary)
                    .lineLimit(1).truncationMode(.middle)
            case .failed(let why):
                Label("Setup didn't finish", systemImage: "xmark.octagon.fill").foregroundStyle(.red).font(.headline)
                Text(why).font(.callout).multilineTextAlignment(.center)
                ScrollView {
                    Text(c.setupLog.suffix(40).joined(separator: "\n"))
                        .font(.caption.monospaced()).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 140).padding(8)
                .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
                Button("Try Again") { c.installEngine() }.buttonStyle(.borderedProminent)
            }
        }
        .padding(40)
        .frame(maxWidth: 500)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct MainView: View {
    var body: some View {
        HStack(spacing: 0) {
            SettingsPane().frame(width: 340)
            Divider()
            QueuePane()
        }
        .safeAreaInset(edge: .bottom, spacing: 0) { BottomBar() }
    }
}

struct SettingsPane: View {
    @EnvironmentObject var c: Converter

    var body: some View {
        Form {
            Section {
                Menu {
                    Section("Recently used") {
                        ForEach(c.recentDevices) { d in
                            Toggle(d.label, isOn: c.selection(d))
                        }
                    }
                    ForEach(DeviceGroup.allCases, id: \.self) { group in
                        Section(group.title) {
                            ForEach(Device.allCases.filter { $0.group == group }) { d in
                                Toggle(d.label, isOn: c.selection(d))
                            }
                        }
                    }
                } label: {
                    Label(c.device.label, systemImage: c.device.symbol)
                }
                .help(c.device.label)
            } header: {
                Text("Make books for")
            } footer: {
                Text("\(c.device.detail).\nBooks are sized for this screen and saved in a folder named after the device.")
                    .foregroundStyle(.secondary)
            }

            if c.anyPanels {
                Section {
                    if c.device == .x4 {
                        Picker("Xteink shades", selection: $c.xteinkFormat) {
                            Text("4 shades (XTCH)").tag("xtch")
                            Text("Black & white (XTC)").tag("xtc")
                        }
                    }
                    Toggle("Show whole page before its panels", isOn: $c.pageFirst)
                    Toggle("Turn wide panels sideways", isOn: $c.rotateWide)
                } header: {
                    Text("One panel per page")
                } footer: {
                    Text("For older Kindles, Kobos, the Xteink X4, Sony and other readers. 4 shades keeps manga screentones; black & white files are half the size. Turning wide panels sideways makes them much bigger; rotate your reader to read them. Pages where the panels can't be found are shown whole.")
                        .foregroundStyle(.secondary)
                }
            }

            Section {
                Picker("Reading direction", selection: $c.rightToLeft) {
                    Text("Right to left").tag(true)
                    Text("Left to right").tag(false)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("Show as a complete page")
                    Text("No zooming or splitting into panels. The cover is each chapter's first page; scanlator credits are usually the last.")
                        .font(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Toggle("Cover", isOn: Binding(
                    get: { c.skipFirst > 0 }, set: { c.skipFirst = $0 ? 1 : 0 }))
                Toggle("Credits", isOn: Binding(
                    get: { c.skipLast > 0 }, set: { c.skipLast = $0 ? 1 : 0 }))
            } header: {
                Text("Pages")
            }

            Section {
                if c.anyKindle {
                    Picker("Kindle format", selection: $c.format) {
                        Text("EPUB").tag("epub")
                        Text("MOBI").tag("mobi")
                    }
                }
                if c.needsKindlegen && !c.hasKindlegen {
                    HStack {
                        Label("Needs Kindle Previewer 4", systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange)
                        Spacer()
                        Button("Get It") { NSWorkspace.shared.open(Converter.previewerURL) }
                    }
                }
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Save to")
                        Spacer()
                        Button("Choose…", action: chooseOutput)
                    }
                    Text(abbreviate(c.output))
                        .font(.caption).foregroundStyle(.secondary)
                        .lineLimit(2).truncationMode(.middle)
                }
                Stepper(value: $c.jobs, in: 1...8) {
                    LabeledContent("Chapters at once", value: "\(c.jobs)")
                }
            } header: {
                Text("Output")
            } footer: {
                Text(deliveryTips)
                    .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .disabled(c.running)
    }

    private var deliveryTips: String {
        switch c.device.group {
        case .kindle:
            c.format == "epub" ? "Send the EPUBs with the Send to Kindle app."
                               : "Copy the MOBIs over USB into the Kindle's documents folder."
        case .olderKindle: "Choose MOBI, then copy the books over USB into the Kindle's documents folder."
        case .kobo: "Copy the CBZ files onto the Kobo over USB."
        case .sony: "Copy the PDFs onto the Reader over USB."
        case .other:
            c.device == .x4 ? "Copy the .\(c.xteinkFormat) files onto the X4's microSD card and open them in CrossPoint."
                            : "CBZ opens in most comic apps and readers."
        }
    }

    private func chooseOutput() {
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = false
        p.canCreateDirectories = true
        p.prompt = "Save Here"
        p.directoryURL = c.output
        if p.runModal() == .OK, let u = p.url { c.output = u }
    }
}

struct QueuePane: View {
    @EnvironmentObject var c: Converter
    @State private var targeted = false

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Queue").font(.title2.bold())
                    Text(summary).font(.callout).foregroundStyle(.secondary).monospacedDigit()
                }
                Spacer()
                if c.queue.contains(where: { $0.state == .done }) {
                    Button("Clear Finished") { c.clearFinished() }
                }
                Button { addWithPanel() } label: { Label("Add…", systemImage: "plus") }
            }
            .padding(.horizontal, 20)
            .padding(.top, 16)
            .padding(.bottom, 12)

            Divider()

            Group {
                if c.queue.isEmpty {
                    EmptyQueueView(targeted: targeted, add: addWithPanel)
                } else {
                    List {
                        ForEach(c.queue) { item in
                            QueueRow(item: item)
                        }
                    }
                    .listStyle(.inset)
                    .alternatingRowBackgrounds()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .overlay {
                if targeted && !c.queue.isEmpty {
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Color.accentColor, lineWidth: 3)
                        .background(Color.accentColor.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                        .padding(6)
                        .allowsHitTesting(false)
                }
            }
            .dropDestination(for: URL.self) { urls, _ in
                c.add(urls)
                return !urls.isEmpty
            } isTargeted: { targeted = $0 }
        }
    }

    private var summary: String {
        if c.queue.isEmpty { return "No titles yet" }
        let titles = "\(c.queue.count) title\(c.queue.count == 1 ? "" : "s")"
        let chapters = c.totalChapters > 0 ? " · \(c.totalChapters) chapters" : ""
        let waiting = c.pendingCount > 0 && c.pendingCount != c.queue.count ? " · \(c.pendingCount) waiting" : ""
        return titles + chapters + waiting
    }

    private func addWithPanel() {
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = true
        p.allowsMultipleSelection = true
        p.allowedContentTypes = [UTType(filenameExtension: "cbz") ?? .zip]
        p.prompt = "Add to Queue"
        p.message = "Choose manga folders or .cbz chapters. Hold ⌘ to pick several."
        if p.runModal() == .OK { c.add(p.urls) }
    }
}

struct EmptyQueueView: View {
    let targeted: Bool
    let add: () -> Void

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "tray.and.arrow.down")
                .font(.system(size: 44, weight: .light))
                .foregroundStyle(.tint)
            Text("Drop manga folders or .cbz files here").font(.title3.weight(.semibold))
            Text("Add as many titles as you like. They're converted one at a time, top to bottom.")
                .font(.callout).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Button("Choose…", action: add).padding(.top, 4)
        }
        .padding(30)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [7, 5]))
                .foregroundStyle(targeted ? Color.accentColor : Color.secondary.opacity(0.35))
                .background(targeted ? Color.accentColor.opacity(0.07) : .clear,
                            in: RoundedRectangle(cornerRadius: 12))
                .padding(20)
        }
    }
}

struct QueueRow: View {
    @EnvironmentObject var c: Converter
    let item: QueueItem
    @State private var showFailures = false

    var body: some View {
        HStack(spacing: 12) {
            statusIcon.frame(width: 22)
            VStack(alignment: .leading, spacing: 3) {
                Text(item.name).font(.body.weight(.medium)).lineLimit(1).truncationMode(.middle)
                if item.state == .running {
                    ProgressView(value: item.progress).controlSize(.small)
                }
                Text(detail).font(.caption).foregroundStyle(.secondary).monospacedDigit().lineLimit(1)
            }
            Spacer(minLength: 12)
            if !item.failures.isEmpty {
                Button("\(item.failures.count) failed") { showFailures = true }
                    .buttonStyle(.link)
                    .foregroundStyle(.orange)
                    .popover(isPresented: $showFailures, arrowEdge: .bottom) { FailureList(item: item) }
            }
            if item.state == .done {
                Button { c.reveal(item) } label: { Image(systemName: "folder") }
                    .buttonStyle(.borderless)
                    .help("Show in Finder")
            }
            if item.state != .running {
                Button { c.remove(item.id) } label: { Image(systemName: "xmark.circle.fill") }
                    .buttonStyle(.borderless)
                    .foregroundStyle(.tertiary)
                    .help("Remove from queue")
            }
        }
        .padding(.vertical, 5)
        .contextMenu {
            Button("Show Source in Finder") { NSWorkspace.shared.activateFileViewerSelecting([item.url]) }
            if item.state == .done { Button("Show Books in Finder") { c.reveal(item) } }
            if item.state != .running {
                Divider()
                Button("Remove from Queue") { c.remove(item.id) }
            }
        }
    }

    @ViewBuilder private var statusIcon: some View {
        switch item.state {
        case .waiting:
            Image(systemName: "clock").foregroundStyle(.secondary)
        case .running:
            ProgressView().controlSize(.small)
        case .stopped:
            Image(systemName: "pause.circle.fill").foregroundStyle(.secondary)
        case .done:
            if item.failures.isEmpty {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
            } else {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
            }
        }
    }

    private var detail: String {
        let chapters: String = {
            guard let n = item.chapterCount else { return "Counting chapters…" }
            if n == 0 { return "No .cbz chapters found" }
            return "\(n) chapter\(n == 1 ? "" : "s")"
        }()
        switch item.state {
        case .waiting:
            return item.chapterCount == nil || item.chapterCount == 0 ? chapters : "\(chapters) · waiting"
        case .running:
            guard let d = item.currentDevice else { return "Starting…" }
            return item.deviceTotal > 0 ? "\(d.label) · \(item.deviceDone) of \(item.deviceTotal)" : "\(d.label) · checking…"
        case .stopped:
            return "\(chapters) · stopped, resumes where it left off"
        case .done:
            var parts: [String] = []
            if item.converted > 0 { parts.append("\(item.converted) book\(item.converted == 1 ? "" : "s") made") }
            if item.alreadyDone > 0 { parts.append("\(item.alreadyDone) already done") }
            if parts.isEmpty { return item.chapterCount == 0 ? chapters : "Nothing new to convert" }
            return parts.joined(separator: " · ")
        }
    }
}

struct FailureList: View {
    let item: QueueItem

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Couldn't convert").font(.headline)
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(item.failures) { f in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(f.chapter) (\(f.device.label))").font(.callout.weight(.medium))
                            Text(f.message).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 260)
        }
        .padding(14)
        .frame(width: 420)
    }
}

struct BottomBar: View {
    @EnvironmentObject var c: Converter

    var body: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 16) {
                if c.running {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(status).font(.callout).monospacedDigit().foregroundStyle(.secondary)
                            .lineLimit(1).truncationMode(.middle)
                        ProgressView(value: c.overallProgress)
                    }
                    Button("Stop") { c.stop() }
                        .controlSize(.large)
                        .help("Chapters that already finished are kept and skipped next time.")
                } else {
                    Text(hint).font(.callout).foregroundStyle(.secondary)
                    Spacer()
                    Button { c.reveal() } label: { Label("Open Output", systemImage: "folder") }
                        .controlSize(.large)
                    Button { c.start() } label: { Text(c.pendingCount > 1 ? "Convert \(c.pendingCount) Titles" : "Convert").frame(minWidth: 90) }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .keyboardShortcut(.defaultAction)
                        .disabled(!c.canStart)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
        }
        .background(.bar)
    }

    private var hint: String {
        if c.queue.isEmpty { return "Drag manga folders or .cbz files into the queue." }
        if c.needsKindlegen && !c.hasKindlegen { return "MOBI needs Kindle Previewer 4." }
        if c.pendingCount == 0 {
            if c.selectedDevices.allSatisfy(\.zooms) {
                return c.format == "epub" ? "All done. Send the books with Send to Kindle."
                                          : "All done. Copy the books to your Kindle's documents folder."
            }
            return "All done. Your books are in the output folder."
        }
        return "\(c.pendingCount) title\(c.pendingCount == 1 ? "" : "s") ready to convert."
    }

    private var status: String {
        let position = c.runCompleted + 1
        let total = c.runCompleted + c.pendingCount + (c.currentItem == nil ? 0 : 1)
        guard let item = c.currentItem else { return "Starting…" }
        var s = "Title \(position) of \(total) · \(item.name)"
        if let d = item.currentDevice, item.deviceTotal > 0 {
            s += " · \(d.label) \(item.deviceDone) of \(item.deviceTotal)"
        }
        return s
    }
}

// MARK: - About

struct AboutView: View {
    private var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0"
    }
    private var bundledKumiko: URL? { Bundle.main.resourceURL?.appendingPathComponent("kumiko") }

    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 6) {
                Image(nsImage: NSApp.applicationIconImage)
                    .resizable().frame(width: 88, height: 88)
                Text("Manga Panel View").font(.title2.bold())
                Text("Version \(version)").font(.callout).foregroundStyle(.secondary)
                Text("Panel-by-panel manga for Kindle and other e-readers.")
                    .font(.callout).padding(.top, 2)
                Link("github.com/MichaelEU/kindlemanga", destination: Links.repo).font(.callout)
            }
            .padding(.top, 22)
            .padding(.bottom, 16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Acknowledgements").font(.headline)
                        Text("This app is built on other people's generous work. Thank you!")
                            .font(.callout).foregroundStyle(.secondary)
                    }

                    Credit(title: "Kumiko", by: "njean42", url: Links.kumiko, license: "AGPL-3.0",
                           text: "Finds the panels on every page and puts them in reading order. Bundled unmodified; its full source ships inside this app.") {
                        if let dir = bundledKumiko {
                            HStack(spacing: 12) {
                                Button("Show Bundled Source") { NSWorkspace.shared.activateFileViewerSelecting([dir]) }
                                Button("View License") { NSWorkspace.shared.open(dir.appendingPathComponent("LICENSE")) }
                            }
                            .buttonStyle(.link).font(.caption)
                        }
                    }

                    Credit(title: "Kindle Comic Converter (KCC)", by: "Ciro Mattia Gonano and contributors",
                           url: Links.kcc, license: "ISC",
                           text: "Showed how Kindle panel view and fixed-layout comic books are put together.") {
                        LicenseNotice(text: kccNotice)
                    }

                    Credit(title: "xtcjs", by: "varo6 and contributors", url: Links.xtcjs, license: "MIT",
                           text: "Its XTC encoder confirmed how Xteink files are laid out.")
                    Credit(title: "CrossPoint Reader", by: "CrossPoint Reader organization", url: Links.crosspoint, license: "MIT",
                           text: "The open-source Xteink firmware. Its decoder showed exactly how 4-shade pages are read, so the files match what the reader expects.")

                    Credit(title: "OpenCV", url: Links.opencv, license: "Apache 2.0",
                           text: "Line and shape detection behind the panel finder.")
                    Credit(title: "NumPy", url: Links.numpy, license: "BSD 3-Clause",
                           text: "Image arrays for OpenCV.")
                    Credit(title: "Pillow", url: Links.pillow, license: "MIT-CMU",
                           text: "Reads, resizes and dithers the pages, writes the PDFs, and drew this app's icon.")
                    Credit(title: "Requests", url: Links.requests, license: "Apache 2.0",
                           text: "Used by Kumiko's command line.")
                    Credit(title: "Amazon",
                           text: "Kindle Previewer and kindlegen build MOBI files, and Send to Kindle delivers the EPUB books. Kindle, Kindle Scribe and Send to Kindle are trademarks of Amazon.com, Inc. or its affiliates. This app is not affiliated with or endorsed by Amazon.")
                    Credit(title: "Claude", by: "Anthropic", url: Links.claudeCode,
                           text: "Designed and written together with Claude, Anthropic's AI assistant, in Claude Code.")

                    Text("And thanks to the manga creators. Please support them by buying official releases.")
                        .font(.callout).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
        }
        .frame(width: 460, height: 580)
    }
}

struct Credit<Extra: View>: View {
    let title: String
    var by: String? = nil
    var url: URL? = nil
    var license: String? = nil
    let text: String
    @ViewBuilder var extra: () -> Extra

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                if let url {
                    Link(title, destination: url).font(.body.weight(.semibold))
                } else {
                    Text(title).font(.body.weight(.semibold))
                }
                Spacer(minLength: 8)
                if let license {
                    Text(license)
                        .font(.caption.weight(.medium))
                        .padding(.horizontal, 7).padding(.vertical, 2)
                        .background(.quaternary, in: Capsule())
                }
            }
            if let by { Text("by \(by)").font(.caption).foregroundStyle(.secondary) }
            Text(text)
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            extra()
        }
    }
}

extension Credit where Extra == EmptyView {
    init(title: String, by: String? = nil, url: URL? = nil, license: String? = nil, text: String) {
        self.init(title: title, by: by, url: url, license: license, text: text, extra: { EmptyView() })
    }
}

struct LicenseNotice: View {
    let text: String
    @State private var expanded = false

    var body: some View {
        DisclosureGroup("License notice", isExpanded: $expanded) {
            Text(text)
                .font(.caption2.monospaced())
                .textSelection(.enabled)
                .padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 6))
        }
        .font(.caption)
    }
}

private let kccNotice = """
ISC LICENSE

Copyright (c) 2012-2025 Ciro Mattia Gonano <ciromattia@gmail.com>
Copyright (c) 2013-2019 Paweł Jastrzębski <pawelj@iosphe.re>
Copyright (c) 2021-2023 Darodi (https://github.com/darodi)
Copyright (c) 2023-2025 Alex Xu (https://github.com/axu2)

Permission to use, copy, modify, and/or distribute this software for
any purpose with or without fee is hereby granted, provided that the
above copyright notice and this permission notice appear in all
copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA
OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

private func abbreviate(_ url: URL) -> String {
    (url.path as NSString).abbreviatingWithTildeInPath
}
