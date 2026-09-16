"""Read-only image evidence, not a visual quality grader. Requires Pillow."""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image, ImageChops, ImageDraw


def rgba8(im):
    # Do not silently quantize high-bit, floating-point or CMYK evidence.
    if im.mode not in {'1', 'L', 'LA', 'P', 'RGB', 'RGBA'}:
        raise ValueError(f'Pixel checks do not support mode {im.mode}; metadata-only is available')
    return im.convert('RGBA')  # resolves palettes AND PNG transparency keys


def rendering_metadata(im):
    # Conversion is not an ICC transform. A metadata change must not pass
    # as unchanged appearance even when decoded channel values are identical.
    return (im.info.get('icc_profile'), im.info.get('gamma'),
            im.info.get('srgb'), im.info.get('chromaticity'),
            im.getexif().get(274, 1))


def box(value):
    values = tuple(int(x) for x in value.split(','))
    if len(values) != 4:
        raise ValueError('Box must have four integers: left,top,right,bottom')
    return values


def checked_box(rect, size):
    x0, y0, x1, y1 = rect
    if not (0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1]):
        raise ValueError(f'Box outside image or empty: {rect}; size={size}')
    return rect


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def white_check(im, mask):
    # Mask is explicitly supplied, never inferred from pixel brightness.
    data = rgba8(im).tobytes()
    selected = exact = transparent = 0
    low = [255, 255, 255]
    high = [0, 0, 0]
    for i, pick in enumerate(mask.tobytes()):
        if not pick:
            continue
        pixel = data[i * 4:i * 4 + 4]
        selected += 1
        exact += pixel == b'\xff\xff\xff\xff'
        transparent += pixel[3] != 255
        for c in range(3):
            low[c] = min(low[c], pixel[c])
            high[c] = max(high[c], pixel[c])
    if not selected:
        raise ValueError('Background selection is empty')
    return dict(selected_pixels=selected, exact_opaque_white_pixels=exact,
                nonopaque_pixels=transparent, channel_min=low, channel_max=high,
                exact_white_fraction=exact / selected, passed=selected == exact,
                scope='Selected decoded RGBA8 pixels only; no ICC transform, whole-background or product-quality pass')


def probe(path, backgrounds=(), background_mask=None, compare=None, protected=(),
          padding_source=None, offset=(0, 0)):
    path = Path(path).resolve()
    with Image.open(path) as opened:
        opened.load()
        im = opened.copy()
        result = dict(schema_version=2, path=str(path), sha256=sha(path),
                      bytes=path.stat().st_size, size=list(im.size), mode=im.mode,
                      format=opened.format, checks={}, visual_quality='not_assessed')
    if backgrounds or background_mask:
        mask = Image.new('L', im.size, 0)
        draw = ImageDraw.Draw(mask)
        for rect in backgrounds:
            x0, y0, x1, y1 = checked_box(rect, im.size)
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
        if background_mask:
            with Image.open(background_mask) as src:
                if src.mode != 'L' or src.size != im.size:
                    raise ValueError('Background mask must be same-size mode L')
                if any(src.histogram()[1:255]):
                    raise ValueError('Background mask must contain only 0 and 255')
                mask = ImageChops.lighter(mask, src)
        result['checks']['selected_background'] = white_check(im, mask)
    if compare:
        if not protected:
            raise ValueError('Comparison requires explicit protected boxes')
        with Image.open(compare) as src:
            if src.size != im.size or src.mode != im.mode:
                raise ValueError('Exact comparison requires equal dimensions and pixel mode')
            a_image, b_image = rgba8(im), rgba8(src)
            metadata_equal = rendering_metadata(src) == rendering_metadata(im)
            rows = []
            for rect in protected:
                checked_box(rect, im.size)
                a, b = a_image.crop(rect).tobytes(), b_image.crop(rect).tobytes()
                changed = sum(x != y for x, y in zip(a, b))
                rows.append(dict(box=list(rect), changed_channel_bytes=changed,
                                 passed=changed == 0 and metadata_equal))
            result['checks']['protected_regions'] = dict(source_sha256=sha(compare), regions=rows,
                                                        comparison='decoded_rgba8_and_rendering_metadata',
                                                        rendering_metadata_equal=metadata_equal,
                                                        passed=all(r['passed'] for r in rows))
    elif protected:
        raise ValueError('Protected boxes require --compare')
    if padding_source:
        with Image.open(padding_source) as src:
            if src.mode != im.mode:
                raise ValueError('Padding identity requires same pixel mode')
            x, y = offset
            rect = checked_box((x, y, x + src.width, y + src.height), im.size)
            equal = rgba8(src).tobytes() == rgba8(im).crop(rect).tobytes()
            metadata_equal = rendering_metadata(src) == rendering_metadata(im)
            mask = Image.new('L', im.size, 255)
            ImageDraw.Draw(mask).rectangle((x, y, rect[2] - 1, rect[3] - 1), fill=0)
            added = im.width * im.height - src.width * src.height
            if not added:
                raise ValueError('No padding pixels exist')
            white = white_check(im, mask)
            result['checks']['padding'] = dict(source_sha256=sha(padding_source), offset=list(offset),
                source_pixels_equal=equal, added_pixels=added, added_white=white,
                comparison='decoded_rgba8_and_rendering_metadata',
                rendering_metadata_equal=metadata_equal,
                passed=equal and metadata_equal and white['passed'],
                scope='Does not certify the original source background, grain or geometry')
    result['all_requested_checks_passed'] = (all(c['passed'] for c in result['checks'].values())
                                             if result['checks'] else None)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image')
    ap.add_argument('--background-box', action='append', default=[], type=box)
    ap.add_argument('--background-mask')
    ap.add_argument('--compare')
    ap.add_argument('--protected-box', action='append', default=[], type=box)
    ap.add_argument('--padding-source')
    ap.add_argument('--offset', default='0,0')
    ap.add_argument('--output', help='New JSON only; refuses overwrite')
    args = ap.parse_args()
    offset = tuple(int(x) for x in args.offset.split(','))
    if len(offset) != 2:
        ap.error('--offset needs x,y')
    try:
        result = probe(args.image, args.background_box, args.background_mask, args.compare,
                       args.protected_box, args.padding_source, offset)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            with Path(args.output).open('x', encoding='utf-8') as f:
                f.write(rendered + '\n')
        print(rendered)
        return 2 if result['all_requested_checks_passed'] is False else 0
    except (ValueError, OSError) as exc:
        ap.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
