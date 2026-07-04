// Offscreen WKWebView screenshot tool — pixel-accurate to the plugin's
// actual rendering engine. usage: shot <url> <w> <h> <out.png> [delaySec]
import Cocoa
import WebKit

struct Config {
    let url: URL
    let w: Int
    let h: Int
    let outPath: String
    let delay: Double
}

func parseArgs() -> Config {
    let args = CommandLine.arguments
    guard args.count >= 5, let url = URL(string: args[1]),
          let w = Int(args[2]), let h = Int(args[3]) else {
        FileHandle.standardError.write("usage: shot <url> <w> <h> <out.png> [delaySec]\n".data(using: .utf8)!)
        exit(2)
    }
    let delay = args.count > 5 ? Double(args[5]) ?? 1.0 : 1.0
    return Config(url: url, w: w, h: h, outPath: args[4], delay: delay)
}

final class Delegate: NSObject, WKNavigationDelegate {
    let config: Config
    init(_ config: Config) { self.config = config }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let config = self.config
        DispatchQueue.main.asyncAfter(deadline: .now() + config.delay) {
            let snap = WKSnapshotConfiguration()
            snap.rect = CGRect(x: 0, y: 0, width: CGFloat(config.w), height: CGFloat(config.h))
            webView.takeSnapshot(with: snap) { image, error in
                guard let image = image,
                      let tiff = image.tiffRepresentation,
                      let rep = NSBitmapImageRep(data: tiff),
                      let png = rep.representation(using: .png, properties: [:]) else {
                    FileHandle.standardError.write("snapshot failed: \(String(describing: error))\n".data(using: .utf8)!)
                    exit(1)
                }
                try? png.write(to: URL(fileURLWithPath: config.outPath))
                print("wrote \(config.outPath)")
                exit(0)
            }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        FileHandle.standardError.write("nav failed: \(error)\n".data(using: .utf8)!)
        exit(1)
    }
}

let config = parseArgs()
let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let webView = WKWebView(frame: NSRect(x: 0, y: 0, width: config.w, height: config.h))
let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: config.w, height: config.h),
                      styleMask: [.borderless], backing: .buffered, defer: false)
window.contentView = webView
window.orderBack(nil)
let delegate = Delegate(config)
webView.navigationDelegate = delegate
webView.load(URLRequest(url: config.url))

DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
    FileHandle.standardError.write("timeout\n".data(using: .utf8)!)
    exit(1)
}
app.run()
