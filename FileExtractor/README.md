# FileExtractor

## Overview

This tool is part of Swift Obfuscator project.

It's developed to parse the Xcode project files (`.xcodeproj` and `.xcworkspace`) and extract the information needed for further steps of obfuscation process. 

The information include the list of files containing the Swift source code that should be obfuscated, the list of frameworks that this code uses and the SDK  that it's working with. The detailed description of what's being extracted by this tool is included in the [data formats](#data-formats) section.

## Usage

```bash
$ file-extractor -projectrootpath <path-to-xcode-project> -filesjson <path-to-output-file>
```

where

`<path-to-xcode-project>` is a path to Xcode project root folder. It\'s the folder that contains both the Xcode project file (.xcodeproj or .xcworkspace) and the source files. It's a required parameter.

`<path-to-output-file>` is a path to the file that the extraced data will be written to. If it's an optional parameter. If ommited, tool will print out to the standard output.

## Data formats

The input data format is defined by the Xcode project file structure and best described [here](http://www.monobjc.net/xcode-project-file-format.html). The user should not need to ever work with it outside of Xcode.

The output data format is called `Files.json` and presented below:

```javascript
{
  "project": {
    "rootPath": <string>
  },
  "module": {
    "name": <string>
  },
  "sdk": {
    "name": <string>
    "path": <string>
  },
  "filenames": [ <string> ]
  "systemLinkedFrameworks": [<string>]
  "explicitelyLinkedFrameworks": [
    {
      "name": <string>,
      "path": <string>
    }
  ]
}
```
`project` is an object that contains the path to the project root directory. This directory will be copied by the Renamer to provide place for writing the obfuscated Swift source files to.

`module` is an object that contains the name of the module that the Swift source code files are part of. It's required for performing the further analysis and will be used to discriminate between the symbols from the external modules (such as linked frameworks) and the symbols that should be obfuscated.

`sdk` is an object that contains both the name and the path to the SDK that the source code will be compiled against. The name is taken from the Xcode project and used as an input for the `xcrun --sdk <sdk.name> --show-sdk-path` to obtain the path to the SDK. Sample names are: `appletvos`, `appletvsimulator`, `iphoneos`, `iphonesimulator`, `macosx`, `watchos`, `watchsimulator`.

`filenames` is an array of paths to files containing the Swift source code that the tool should obfuscate.

`systemLinkedFrameworks` contains the list of names of frameworks that are imported in the source code (with various form of Swift `import` statement), but not included in the Xcode project. Since Xcode autolinks the system frameworks by default (see `CLANG_MODULES_AUTOLINK` flag), these frameworks should be automatically found by the compiler, which uses the SDK path for this purpose. They are used to identify the module that the symbol is part of.

`explicitelyLinkedFrameworks` contains the list of framework objects with name and path. These are taken from the Xcode project, which must contain the names and paths to frameworks that are not automatically linked. They are required for the Swift compiler to perform the analysis and also used to identify which module is the symbol part of.

Sample `Files.json` file might look like that:

```javascript
{
   "project": {
       "rootPath": "/Users/siejkowski/Polidea/SwiftObfuscator/TestProjects/macOSTestApp"
   },
   "module": {
      "name":"macOSTestApp"
   },
   "sdk": {
      "name":"macosx",
      "path":"/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.13.sdk"
   },
   "filenames": [
      "/Users/siejkowski/Polidea/SwiftObfuscator/TestProjects/macOSTestApp/macOSTestApp/ViewController.swift",
      "/Users/siejkowski/Polidea/SwiftObfuscator/TestProjects/macOSTestApp/macOSTestApp/AppDelegate.swift"
   ],
   "explicitelyLinkedFrameworks": [
      {
         "name":"CoreImage",
         "path":"/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.13.sdk/System/Library/Frameworks/"
      }
   ],
   "systemLinkedFrameworks":[
      "Cocoa"
   ]
}
```

## Feature list

- [] TBA

## Build notes for developers

1. Clone the File Extractor source  
   `git clone ssh://git@gitlab2.polidea.com:23/SwiftObfuscator/FileExtractor.git`

2. Install the tool for managing the Ruby versions (rbenv)  
   `brew install rbenv`

3. Initialize the tool for managing the Ruby versions in your shell of choice  
   for Bash: `eval $(rbenv init -)`  
   for Fish: `eval (rbenv init -)`

4. (optional) Verify, that the tool for managing the Ruby versions is properly setup  
   `curl -fsSL https://github.com/rbenv/rbenv-installer/raw/master/bin/rbenv-doctor | bash`

5. Install Ruby in a required version 2.2.2  
   `rbenv install 2.2.2`

6. Install bundler  
   `gem install bundler`

7. Install dependencies  
   `bundle install --binstubs`

8. Run application to verify that everything went well  
   run application: `ruby /bin/file-extractor`  
   run tests: `/bin/bash Scripts/run_all_tests.sh`

9. If you're using VisualStudio Code as IDE, please ensure that the `rbenv init` is properly added to your profile   
   for Bash: `.bashprofile` should contain `eval "$(rbenv init -)"`  
   for Fish: `.config/fish/config.fish` should contain `status --is-interactive; and source (rbenv init -|psub)`  
   for zsh:  `.zshrc` should contain:  
   `export PATH="$HOME/.rbenv/bin:$PATH"`  
   `eval "$(rbenv init -)"`  
   Please consult `https://github.com/rbenv/rbenv/issues/815` for more information.

10. If you're building for further distribution, run the package preparing tool  
   `bundle exec rake package:osx`  
   Note: parameter DIR_ONLY=1 makes the rake generate the directory with package, not the archived package

## On project dependencies

The application itself is written in Ruby. The application launcher is written in Swift.

Tool uses three main dependencies. From these dependencies the distribution format occures.

First one is [Xcodeproj](https://github.com/CocoaPods/Xcodeproj), which is a part of [Cocoapods](https://cocoapods.org) project. This is a Ruby gem for working with Xcode project files. It's used to extract all the possible information from the project files.

The second one is `xcrun`, which is a part of Xcode command line tools. It's used for determining the SDK path.

The third one is Swift compiler tool called `swiftc`. It's used to extract the information about the modules imported in the Swift source code files.

These dependencies determined the way that the project is build and distributed.

We want to limit the number of environment settings that the user must provide for the tool to work. However, we're using a Ruby gem that requires a Ruby interpreted installed on the user side in a proper version as well as number of other Ruby dependencies. To dodge the problems on the user side, we're using the [Travelling Ruby](http://phusion.github.io/traveling-ruby/) project and package the tool together with its own Ruby interpreter and all the required dependencies. This way the user doesn't need to know about the existance of Ruby as the underlying technology.

The existence of `xcrun` and `swiftc` in the user environment is right now implicitely expected. 

Future works might allow for reducing the number of dependencies, for example by supplying some information (such as SDK path) directly from the user.

## Further read

Please consult the [Documentation](Documentation/) folder for the further explanations.

## Licence

TBA

## Contributors

In the alphabetical order:

* [Jerzy Kleszcz](mailto:jerzy.kleszcz@polidea.com)
* [Krzysztof Siejkowski](krzysztof.siejkowski@polidea.com)
