; -- Example1.iss --
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Picty
AppVersion=0.5
AppPublisher=Damien Moore
AppPublisherURL=http://launchpad.net/picty
DefaultDirName={pf}\picty
DefaultGroupName=picty
UninstallDisplayIcon={app}\picty.exe
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=picty-0.5-setup

[Dirs]
Name: {app}; Flags: uninsalwaysuninstall;

[Files]
Source: dist\*; DestDir: {app}; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\picty"; Filename: "{app}\picty.exe"
;Name: {group}\handytool; Filename: {app}\handytool.exe; WorkingDir: {app}

[Run]
; If you are using GTK's built-in SVG support, uncomment the following line.
;Filename: {cmd}; WorkingDir: "{app}"; Parameters: "/C gdk-pixbuf-query-loaders.exe > lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"; Description: "GDK Pixbuf Loader Cache Update"; Flags: nowait runhidden
Filename: {app}\picty.exe; Description: {cm:LaunchProgram,picty}; Flags: nowait postinstall skipifsilent



