import Cocoa
import CoreGraphics
import Foundation

func postKey(keyCode: CGKeyCode, commandDown: Bool = false) {
    let source = CGEventSource(stateID: .hidSystemState)
    
    guard let keyDown = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: true),
          let keyUp = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: false) else {
        return
    }
    
    if commandDown {
        keyDown.flags = .maskCommand
        keyUp.flags = .maskCommand
    }
    
    keyDown.post(tap: .cghidEventTap)
    keyUp.post(tap: .cghidEventTap)
}

let args = CommandLine.arguments

if args.count < 2 {
    print("Usage: typer [backspace <count>] | [paste]")
    exit(1)
}

let command = args[1]

if command == "backspace" {
    let count = args.count > 2 ? (Int(args[2]) ?? 1) : 1
    for _ in 0..<count {
        postKey(keyCode: 51) // 51 is backspace
        Thread.sleep(forTimeInterval: 0.005)
    }
} else if command == "paste" {
    postKey(keyCode: 9, commandDown: true) // 9 is 'v'
} else {
    print("Unknown command")
    exit(1)
}
