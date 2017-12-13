from __future__ import absolute_import, division

import AppKit
import Quartz

import os

from .pdfContext import PDFContext
from .baseContext import Color


def _nsDataConverter(value):
    if isinstance(value, AppKit.NSData):
        return value
    return AppKit.NSData.dataWithBytes_length_(value, len(value))


def _nsColorConverter(color):
    if isinstance(color, AppKit.NSColor):
        return color
    color = Color(*color)
    return color.getNSObject()


def _tiffCompressionConverter(value):
    if value is None:
        return AppKit.NSTIFFCompressionNone
    elif isinstance(value, int):
        return value
    else:
        t = dict(lzw=AppKit.NSTIFFCompressionLZW, packbits=AppKit.NSTIFFCompressionPackBits)
        return t.get(value.lower(), AppKit.NSTIFFCompressionNone)


_nsImageOptions = [
    # DrawBot Key                    NSImage property key                   converter or None   doc
    ("imageColorSyncProfileData",    AppKit.NSImageColorSyncProfileData,    _nsDataConverter,          "A bytes or NSData object containing the ColorSync profile data."),
    ("imageJPEGCompressionFactor",   AppKit.NSImageCompressionFactor,       None,                      "A float between 0.0 and 1.0, with 1.0 resulting in no compression and 0.0 resulting in the maximum compression possible"),  # number
    ("imageTIFFCompressionMethod",   AppKit.NSImageCompressionMethod,       _tiffCompressionConverter, "None, or 'lzw' or 'packbits', or an NSTIFFCompression constant"),
    ("imageGIFDitherTransparency",   AppKit.NSImageDitherTransparency,      None,                      "Boolean that indicates whether the image is dithered"),
    #("imageJPEGEXIFData",           AppKit.NSImageEXIFData,                None,                      ""),  # dict  XXX Doesn't seem to work
    ("imageFallbackBackgroundColor", AppKit.NSImageFallbackBackgroundColor, _nsColorConverter,         "The background color to use when writing to an image format (such as JPEG) that doesn't support alpha. The color's alpha value is ignored. The default background color, when this property is not specified, is white. The value of the property should be an NSColor object or a DrawBot RGB color tuple."),
    ("imagePNGGamma",                AppKit.NSImageGamma,                   None,                      "The gamma value for the image. It is a floating-point number between 0.0 and 1.0, with 0.0 being black and 1.0 being the maximum color."),
    ("imagePNGInterlaced",           AppKit.NSImageInterlaced,              None,                      "Boolean value that indicates whether the image should be interlaced."),  # XXX doesn't seem to work
    ("imageJPEGProgressive",         AppKit.NSImageProgressive,             None,                      "Boolean that indicates whether the image should use progressive encoding."),
    ("imageGIFRGBColorTable",        AppKit.NSImageRGBColorTable,           _nsDataConverter,          "A bytes or NSData object containing the RGB color table."),
]


class ImageContext(PDFContext):

    _saveImageFileTypes = {
        "jpg": AppKit.NSJPEGFileType,
        "jpeg": AppKit.NSJPEGFileType,
        "tiff": AppKit.NSTIFFFileType,
        "tif": AppKit.NSTIFFFileType,
        # "gif": AppKit.NSGIFFileType,
        "png": AppKit.NSPNGFileType,
        "bmp": AppKit.NSBMPFileType
    }

    fileExtensions = _saveImageFileTypes.keys()

    saveImageOptions = PDFContext.saveImageOptions + [
        ("imageResolution", "The resolution of the output image in PPI. Default is 72."),
    ]
    saveImageOptions.extend((dbKey, doc) for dbKey, nsKey, converter, doc in _nsImageOptions)

    def _writeDataToFile(self, data, path, options):
        multipage = options.get("multipage")
        if multipage is None:
            multipage = False
        fileName, fileExt = os.path.splitext(path)
        ext = fileExt[1:]
        pdfDocument = Quartz.PDFDocument.alloc().initWithData_(data)
        firstPage = 0
        pageCount = pdfDocument.pageCount()
        pathAdd = "_1"
        if not multipage:
            firstPage = pageCount - 1
            pathAdd = ""
        outputPaths = []
        imageResolution = options.get("imageResolution", 72.0)
        properties = {}
        for dbKey, nsKey, converter, doc in _nsImageOptions:
            if dbKey in options:
                value = options[dbKey]
                if converter is not None:
                    value = converter(value)
                properties[nsKey] = value
        for index in range(firstPage, pageCount):
            pool = AppKit.NSAutoreleasePool.alloc().init()
            try:
                page = pdfDocument.pageAtIndex_(index)
                image = AppKit.NSImage.alloc().initWithData_(page.dataRepresentation())
                imageRep = _makeBitmapImageRep(image, imageResolution)
                imageData = imageRep.representationUsingType_properties_(self._saveImageFileTypes[ext], properties)
                imagePath = fileName + pathAdd + fileExt
                imageData.writeToFile_atomically_(imagePath, True)
                pathAdd = "_%s" % (index + 2)
                outputPaths.append(imagePath)
                del page, imageRep, imageData
            finally:
                del pool
        return outputPaths


def _makeBitmapImageRep(image, imageResolution=72.0):
    """Construct a bitmap image representation at a given resolution."""
    scaleFactor = max(1.0, imageResolution) / 72.0
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None,                                   # planes
        int(image.size().width * scaleFactor),  # pixelsWide
        int(image.size().height * scaleFactor), # pixelsHigh
        8,                                      # bitsPerSample
        4,                                      # samplesPerPixel
        True,                                   # hasAlpha
        False,                                  # isPlanar
        AppKit.NSDeviceRGBColorSpace,           # colorSpaceName
        0,                                      # bytesPerRow
        0                                       # bitsPerPixel
    )
    rep.setSize_(image.size())

    AppKit.NSGraphicsContext.saveGraphicsState()
    try:
        AppKit.NSGraphicsContext.setCurrentContext_(
            AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
        image.drawAtPoint_fromRect_operation_fraction_((0, 0), AppKit.NSZeroRect, AppKit.NSCompositeSourceOver, 1.0)
    finally:
        AppKit.NSGraphicsContext.restoreGraphicsState()
    return rep
