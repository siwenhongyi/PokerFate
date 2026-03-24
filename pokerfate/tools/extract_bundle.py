"""
Extract assets from Unity Asset Bundle.
Usage: python -m pokerfate.tools.extract_bundle [bundle_path] [output_dir]
"""
import os
import sys
import UnityPy


DEFAULT_BUNDLE = "pokerfate_extracted/assets/aa/Android/gameres_assets_proto_054630f729605b320ebe368895964f28.bundle"
DEFAULT_OUTPUT = "proto_extracted"


def extract(bundle_path: str, output_dir: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    env = UnityPy.load(bundle_path)
    exported = []

    for path, obj in env.container.items():
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        filename = path.split("/")[-1]
        out_path = os.path.join(output_dir, filename)
        raw = bytes(data.script)
        with open(out_path, "wb") as f:
            f.write(raw)
        exported.append(out_path)
        print(f"  {filename}  ({len(raw)} bytes)")

    return exported


def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BUNDLE
    output_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT

    print(f"Bundle : {bundle_path}")
    print(f"Output : {output_dir}")
    print()

    files = extract(bundle_path, output_dir)
    print(f"\n{len(files)} file(s) exported to {output_dir}/")


if __name__ == "__main__":
    main()
