'''
metadata.py

This module describes the exif, iptc and xmp metadata used by the program
and provides a dictionary to handle conversion between exiv2 formats and internal
representation
'''

import pyexiv2

import gtk
##todo: reimplement for xmp support
##e.g. merge Iptc.Application2.Keywords with Xmp.dc.subject



def load_metadata(item,filename=None,thumbnail=False):
    if item.meta==False:
        return
    try:
        if not filename:
            filename=item.filename
        rawmeta = pyexiv2.Image(filename)
        rawmeta.readMetadata()
        item.meta=dict()
        get_exiv2_meta(item.meta,rawmeta)
        if thumbnail:
            try:
                ttype,tdata=rawmeta.getThumbnailData()
                pbloader = gtk.gdk.PixbufLoader() ##todo: gtk stuff doesn't belong here -- shift it to image manip (i.e. just return the binary data)
                pbloader.write(tdata)
                pb=pbloader.get_pixbuf()
                pbloader.close()
                w=pb.get_width()
                h=pb.get_height()
                a=max(128,w,h)
                item.thumb=pb.scale_simple(128*w/a,128*h/a,gtk.gdk.INTERP_BILINEAR)
            except:
                print 'Load thumbnail failed',item.filename
                import traceback,sys
                print traceback.format_exc(sys.exc_info()[2])
                item.thumb=None
    except:
        print 'Error reading metadata for',filename
        import traceback,sys
        print traceback.format_exc(sys.exc_info()[2])
        item.meta=False
    item.mark_meta_saved()
    return True


def save_metadata(item):
    if item.meta==False:
        return False
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        set_exiv2_meta(item.meta,rawmeta)
        rawmeta.writeMetadata()
        item.mark_meta_saved()
    except:
        print 'Error writing metadata for',item.filename
        import traceback,sys
        print traceback.format_exc(sys.exc_info()[2])
        return False
    return True


def copy_metadata(src_item,destination_file):
    '''
    copy metadata from a source item to a destination file
    due to bugs in pyexiv2|exiv2, only the metadata in the
    module list 'apptags' are written
    '''
    print 'copy metadata'
    if src_item.meta==False:
        return False
    try:
        print 'reading src_item metadata'
        rawmeta_src = pyexiv2.Image(src_item.filename)
        rawmeta_src.readMetadata()
    except:
        print 'Error reading metadata for',src_item.filename
        return False
    try:
        rawmeta_dest = pyexiv2.Image(destination_file)
        rawmeta_dest.readMetadata()
        for k in rawmeta_src.exifKeys():
            try:
                if k in appkeys:
                    rawmeta_dest[k]=rawmeta_src[k]
            except:
                pass
        for k in rawmeta_src.iptcKeys():
            try:
                if k in appkeys:
                    rawmeta_dest[k]=rawmeta_src[k]
            except:
                pass
        set_exiv2_meta(src_item.meta,rawmeta_dest)
        rawmeta_dest.writeMetadata()
    except:
        print 'Error changing metadata in destination file',destination_file
    return True


def save_metadata_key(item,key,value):
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        rawmeta[key]=value
        rawmeta.writeMetadata()
    except:
        print 'Error writing metadata for',item.filename




##The conv functions take a key and return a string representation of the metadata OR if value!=None convert the string value to a set of (metadata_key,value) tag pairs

def conv_date_taken(metaobject,keys,value=None):
    if value!=None:
        return True
    date=None
###    if "Iptc.Application2.DateCreated" in metaobject.exifKeys() and "Iptc.Application2.TimeCreated" in metaobject.exifKeys():
###        date=str(metaobject["Iptc.Application2.DateCreated"])+' '+str(metaobject["Iptc.Application2.TimeCreated"])
###        date=datetime.strptime(date)
    if "Exif.Photo.DateTimeOriginal" in metaobject.exifKeys():
        date=metaobject["Exif.Photo.DateTimeOriginal"]
        if type(date)==str:
            date=datetime.strptime(date)
    return date

def conv_str(metaobject,keys,value=None):
    if value!=None:
        if keys[0] in metaobject.iptcKeys() or keys[0] in metaobject.exifKeys() or value!='':
            metaobject[keys[0]]=value
        ##todo: change or empty other keys
        return True
    for k in keys:
        try:
            val=metaobject[k]
            return str(val)
        except:
            pass
    return None

def conv_int(metaobject,keys,value=None):
    if value!=None:
        if keys[0] in metaobject.iptcKeys() or keys[0] in metaobject.exifKeys() or value!=-1:
            metaobject[keys[0]]=value
        ##todo: change or empty other keys
        return True
    for k in keys:
        try:
            val=metaobject[k]
            return int(val)
        except:
            pass
    return None

def tag_split(tag_str):
    quoted=False
    tags=[]
    curtag=''
    for x in tag_str:
        if x=='"':
            quoted=not quoted
            if quoted and curtag:
                tags.append(curtag)
                curtag=''
            continue
        if (x==' ' or x=='\n') and not quoted:
            if curtag:
                tags.append(curtag)
                curtag=''
            continue
        curtag+=x
    if curtag:
        tags.append(curtag)
    return tags

def tag_bind(tags,sep=' '):
    pretag=[]
    for tag in tags:
        if ' ' in tag:
            tag='"%s"'%(tag,)
        pretag.append(tag)
    return sep.join(pretag)

def conv_keywords(metaobject,keys,value=None):
    if value!=None:
        if (keys[0] in metaobject.iptcKeys() or keys[0] in metaobject.exifKeys()) or len(value)>0:
            metaobject["Iptc.Application2.Keywords"]=value
        return True
    try:
        val=metaobject["Iptc.Application2.Keywords"]
        if type(val)==str:
            return [val]
        return list(val)
    except:
        return None ##the fallback to UserComment is disabled for now
        try:
            #parse 'abc "def ghi" fdg' as three tags -- need quote parsing
            val=metaobject["Exif.Photo.UserComment"] ##TODO: This object is not a string, but a bytestream! Need to do conversion + encoding detection - YUK!
            vals=tag_split(val)
            return vals
        except:
            return None

def conv_rational(metaobject,keys,value=None):
    if value!=None:
        if keys[0] in metaobject.iptcKeys() or keys[0] in metaobject.exifKeys() and len(value)>0:
            ##todo: change or empty other keys
            try:
                if type(value)==str:
                    metaobject[keys[0]]=value
                    return True
                if type(value)==tuple:
                    metaobject[keys[0]]='%i/%i'%value
                    return True
            except:
                pass
        return True
    for k in keys:
        try:
            val=metaobject[k]
            try:
                return (int(val[0]),int(val[1]))
            except:
                vals=str(val).split('/')
                return (int(vals[0]),int(vals[1]))
        except:
            pass
    return None

def coords_as_rational(decimal):
    print 'converting coords to rational',decimal
    decimal=abs(decimal)
    degree=int(decimal)
    minute=int((decimal-degree)*60)
    second=int((decimal-degree-minute/60)*3600*100000)
    print 'coords',degree,minute,second
    return (pyexiv2.Rational(degree,1),pyexiv2.Rational(minute,1),pyexiv2.Rational(second,100000))
    print 'coords',degree,minute,second

def coords_as_decimal(rational):
    if type(rational) in (list,tuple):
        deci=1.0*rational[0].numerator/rational[0].denominator
        if len(rational)>1:
            deci+=1.0*rational[1].numerator/rational[1].denominator/60
        if len(rational)>2:
            deci+=1.0*rational[2].numerator/rational[2].denominator/3600
        return deci
    if type(rational) == pyexiv2.Rational:
        return 1.0*rational.numerator/rational.denominator
    raise TypeError

def conv_latlon(metaobject,keys,value=None):
    if value!=None:
        lat,lon=value
        rat_lat=coords_as_rational(lat)##(int(abs(lat)*1000000),1000000)
        rat_lon=coords_as_rational(lon)##(int(abs(lon)*1000000),1000000)
        latref='N' if lat>=0 else 'S'
        lonref='E' if lon>=0 else 'W'
        metaobject[keys[0]]=rat_lat
        metaobject[keys[1]]=latref
        metaobject[keys[2]]=rat_lon
        metaobject[keys[3]]=lonref
        print 'wrote latlon'
    else:
        try:
            rat_lat=metaobject[keys[0]]
            latref=metaobject[keys[1]]
            rat_lon=metaobject[keys[2]]
            lonref=metaobject[keys[3]]
            lat=(1.0 if latref=='N' else -1.0)*coords_as_decimal(rat_lat)
            lon=(1.0 if lonref=='E' else -1.0)*coords_as_decimal(rat_lon)
            return (lat,lon)
        except:
            return None

def tup2str(value):
    try:
        return '%3.6f;%3.6f'%value
    except:
        return ''

def str2tup(value):
    vals=value.split(';')
    return (float(vals[0]),float(vals[1]))

def str2rat(value):
    vals=value.split('/')
    return (int(vals[0]),int(vals[1]))

def rat2str(value):
    return '%i/%i'%value

def rational_as_float(value_tuple):
    return 1.0*value_tuple[0]/value_tuple[1]

def date_as_sortable(date_value):
    if date_value:
        return date_value
    return datatime.date(1900,1,1)

'''
apptags defines the exif metadata kept in the cache.
the data are created from and written to the item.
each entry in the tuple is itself a tuple containing:
 * The short name of the tag (to be used in the program)
 * The display name of the tag
 * User Editable (TRUE/FALSE) in a gtk.Entry
 * The callback to convert to the container format (exiv2) and the
    preferred representation of this app (tuple, str, datetime, int, float)
 * A function to convert the internal rep to a string
 * A function to convert a string to the internal rep
 * A function to convert the key to a sortable
 * A tuple of EXIF, IPTC and XMP tags from which to fill the app tag (passed to the callback)
'''

apptags=(
("DateTaken","Date Taken",False,conv_date_taken,None,None,date_as_sortable,(("Iptc.Application2.DateCreated","Iptc.Application2.TimeCreated"),"Exif.Photo.DateTimeOriginal",)),
("Title","Title",True,conv_str,None,None,None,("Iptc.Application2.Headline",)),
("ImageDescription","Image Description",True,conv_str,None,None,None,("Iptc.Application2.Caption","Exif.Image.ImageDescription",)),
("Keywords","Tags",True,conv_keywords,tag_bind,tag_split,None,("Iptc.Application2.Keywords","Exif.Photo.UserComment")),
("Artist","Artist",True,conv_str,None,None,None,("Iptc.Application2.Credit","Exif.Image.Artist")),
("Copyright","Copyright",True,conv_str,None,None,None,("Iptc.Application2.Copyright","Exif.Image.Copyright",)),
#("Rating",True,conv_int,("Xmp.xmp.Rating")),
("Album","Album",True,conv_str,None,None,None,("Iptc.Application2.Subject",)),
("Make","Make",False,conv_str,None,None,None,("Exif.Image.Make",)),
("Model","Model",False,conv_str,None,None,None,("Exif.Image.Model",)),
("Orientation","Orientation",False,conv_int,str,int,None,("Exif.Image.Orientation",)),
("ExposureTime","Exposure Time",False,conv_rational,rat2str,str2rat,rational_as_float,("Exif.Photo.ExposureTime",)),
("FNumber","FNumber",False,conv_rational,rat2str,str2rat,rational_as_float,("Exif.Photo.FNumber",)),
("IsoSpeed","Iso Speed",False,conv_int,str,int,None,("Exif.Photo.ISOSpeedRatings",)),
("FocalLength","Focal Length",False,conv_rational,rat2str,str2rat,rational_as_float,("Exif.Photo.FocalLength",)),
("ExposureProgram","Exposure Program",False,conv_str,None,None,None,("Exif.Photo.ExposureProgram",)),
("ExposureBiasValue","Exposure Bias Value",False,conv_str,None,None,None,("Exif.Photo.ExposureBiasValue",)),
("MeteringMode","Metering Mode",False,conv_str,None,None,None,("Exif.Photo.MeteringMode",)),
("Flash","Flash",False,conv_str,None,None,None,("Exif.Photo.Flash",)),
("SensingMethod","Sensing Method",False,conv_str,None,None,None,("Exif.Photo.SensingMethod",)),
("ExposureMode","Exposure Mode",False,conv_str,None,None,None,("Exif.Photo.ExposureMode",)),
("WhiteBalance","White Balance",False,conv_str,None,None,None,("Exif.Photo.WhiteBalance",)),
("DigitalZoomRatio","Digital Zoom Ratio",False,conv_str,None,None,None,("Exif.Photo.DigitalZoomRatio",)),
("SceneCaptureType","Scene Capture Type",False,conv_str,None,None,None,("Exif.Photo.SceneCaptureType",)),
("GainControl","Gain Control",False,conv_str,None,None,None,("Exif.Photo.GainControl",)),
("Contrast","Contrast",False,conv_str,None,None,None,("Exif.Photo.Contrast",)),
("Saturation","Saturation",False,conv_str,None,None,None,("Exif.Photo.Saturation",)),
("Sharpness","Sharpness",False,conv_str,None,None,None,("Exif.Photo.Sharpness",)),
("SubjectDistanceRange","Subject Distance",False,conv_str,None,None,None,("Exif.Photo.SubjectDistanceRange",)),
("Software","Software",False,conv_str,None,None,None,("Exif.Image.Software",)),
("IPTCNAA","IPTCNAA",False,conv_str,None,None,None,("Exif.Image.IPTCNAA",)),
("ImageUniqueID","Image Unique ID",False,conv_str,None,None,None,("Exif.Photo.ImageUniqueID",)),
("Processing Software","Processing Software",False,conv_str,None,None,None,("Exif.Image.ProcessingSoftware",)),
("LatLon","Geolocation",False,conv_latlon,tup2str,str2tup,None,("Exif.GPSInfo.GPSLatitude","Exif.GPSInfo.GPSLatitudeRef","Exif.GPSInfo.GPSLongitude","Exif.GPSInfo.GPSLongitudeRef")),
##("GPSTimeStamp","GPSTimeStamp",False,must convert a len 3 tuple of rationals("Exif.GPSInfo.GPSTimeStamp",))
)

##todo: remove this item -- currently used to define the keys to write in imagemanip.save_metadata
writetags=[(x[0],x[1]) for x in apptags if x[3]]
writetags.append(('Orientation','Orientation'))

apptags_dict=dict([(x[0],x[1:]) for x in apptags])
appkeys=[y for x in apptags for y in x[7]]

def get_exiv2_meta(app_meta,exiv2_meta):
    for appkey,data in apptags_dict.iteritems():
        try:
            val=data[2](exiv2_meta,data[6])
            if val:
                app_meta[appkey]=val
        except:
            pass

def set_exiv2_meta(app_meta,exiv2_meta):
    for appkey in app_meta:
        try:
            data=apptags_dict[appkey]
            data[2](exiv2_meta,data[6],app_meta[appkey])
        except:
            print 'exiv2 set data failure',appkey

def app_key_from_string(key,string):
    fn=apptags_dict[key][4]
    if fn:
        try:
            return fn(string)
        except:
            return None
    else:
        return string

def app_key_to_string(key,value):
    try:
        return apptags_dict[key][3](value)
    except:
        try:
            return str(value)
        except:
            return None

def app_key_as_sortable(app_meta,key):
    if apptags_dict[key][5]!=None:
        try:
            return apptags_dict[key][5](app_meta[key])
        except:
            return None
    else:
        try:
            return app_meta[key]
        except:
            return None

#apptags=(
#("DateTaken","Date Taken",False,conv_date_taken,(("Iptc.Application2.DateCreated","Iptc.Application2.TimeCreated"),"Exif.Photo.DateTimeOriginal",)),
#("Title","Title",True,conv_str,("Xmp.dc.title",)),
#("ImageDescription","Image Description",True,conv_str,("Xmp.dc.description","Iptc.Application2.Caption","Exif.Image.ImageDescription",)),
#("Tags","Tags",True,conv_keywords,("Xmp.dc.subject","Iptc.Application2.Keywords","Exif.Photo.UserComment")),
#("Artist","Artist",True,conv_str,("Iptc.Application2.Credit","Exif.Image.Artist")),
#("Copyright","Copyright",True,conv_str,("Iptc.Application2.Copyright","Exif.Image.Copyright",)),
#("Rating",True,conv_int,("Xmp.xmp.Rating")),
#("Album",True,conv_str,("Xmp.xmp.Label","Iptc.Application2.Subject")),
#("Make","Make",False,conv_str,("Exif.Image.Make",)),
#("Model","Model",False,conv_str,("Exif.Image.Model",)),
#("Orientation","Orientation",False,conv_int_tuple,("Exif.Image.Orientation",)),
#("Exposure Time","Exposure Time",False,conv_int_tuple,("Exif.Photo.ExposureTime",)),
#("FNumber","FNumber",False,conv_int_tuple,("Exif.Photo.FNumber",)),
#("ExposureProgram","ExposureProgram",False,conv_str,("Exif.Photo.ExposureProgram",)),
#("ExposureBiasValue","ExposureBiasValue",False,conv_str,("Exif.Photo.ExposureBiasValue",)),
#("MeteringMode","MeteringMode",False,conv_str,("Exif.Photo.MeteringMode",)),
#("Flash","Flash",False,conv_str,("Exif.Photo.Flash",)),
#("FocalLength","FocalLength",False,conv_str,("Exif.Photo.FocalLength",)),
#("SensingMethod","SensingMethod",False,conv_str,("Exif.Photo.SensingMethod",)),
#("ExposureMode","ExposureMode",False,conv_str,("Exif.Photo.ExposureMode",)),
#("WhiteBalance","WhiteBalance",False,conv_str,("Exif.Photo.WhiteBalance",)),
#("DigitalZoomRatio","DigitalZoomRatio",False,conv_str,("Exif.Photo.DigitalZoomRatio",)),
#("SceneCaptureType","SceneCaptureType",False,conv_str,("Exif.Photo.SceneCaptureType",)),
#("GainControl","GainControl",False,conv_str,("Exif.Photo.GainControl",)),
#("Contrast","Contrast",False,conv_str,("Exif.Photo.Contrast",)),
#("Saturation","Saturation",False,conv_str,("Exif.Photo.Saturation",)),
#("Sharpness","Sharpness",False,conv_str,("Exif.Photo.Sharpness",)),
#("SubjectDistanceRange","SubjectDistanceRange",False,conv_str,("Exif.Photo.SubjectDistanceRange",)),
#("Software","Software",False,conv_str,("Exif.Image.Software",)),
#("IPTCNAA","IPTCNAA",False,conv_str,("Exif.Image.IPTCNAA",)),
#("ImageUniqueID","ImageUniqueID",False,conv_str,("Exif.Photo.ImageUniqueID",)),
#("Processing Software","Processing Software",conv_str,False,("Exif.Image.ProcessingSoftware",))
#)




#tag tuples: long name, short name, writeable
tags=(
#("Exif.Image.DateTime","DateTime"),
("Exif.Photo.DateTimeOriginal","DateTimeOriginal",False),
("Exif.Photo.DateTimeDigitized","DateTimeDigitized",False),
#("Exif.Image.DocumentName","Document Name"),
("Xmp.dc.title","Title",True),
("Exif.Image.ImageDescription","Image Description",True),
("Xmp.dc.subject","Tags",True),
("Iptc.Application2.Keywords","Keywords",True),
("Exif.Photo.UserComment","UserComment",True),
("Exif.Image.Artist","Artist",True),
("Exif.Image.Copyright","Copyright",True),
("Exif.Image.Make","Make",False),
("Exif.Image.Model","Model",False),
("Exif.Image.ImageWidth","Width",False),
("Exif.Image.ImageLength","Height",False),
("Exif.Image.Orientation","Orientation",False),
("Exif.Photo.ExposureTime","Exposure Time",False),
("Exif.Photo.FNumber","FNumber",False),
("Exif.Pentax.ISO","ISO Speed",False),
("Exif.Photo.ExposureProgram","ExposureProgram",False),
#("Exif.Photo.ShutterSpeedValue","ShutterSpeedValue"),
#("Exif.Photo.ApertureValue","ApertureValue"),
#("Exif.Photo.BrightnessValue","BrightnessValue"),
("Exif.Photo.ExposureBiasValue","ExposureBiasValue",False),
#("Exif.Photo.MaxApertureValue","MaxApertureValue"),
#("Exif.Photo.SubjectDistance","SubjectDistance"),
("Exif.Photo.MeteringMode","MeteringMode",False),
#("Exif.Photo.LightSource","LightSource"),
("Exif.Photo.Flash","Flash",False),
("Exif.Photo.FocalLength","FocalLength",False),
#("Exif.Photo.SubjectArea","SubjectArea"),
#("Exif.Photo.RelatedSoundFile","RelatedSoundFile"),
#("Exif.Photo.FlashEnergy","FlashEnergy"),
#("Exif.Photo.SubjectLocation","SubjectLocation"),
#("Exif.Photo.ExposureIndex","ExposureIndex"),
("Exif.Photo.SensingMethod","SensingMethod",False),
("Exif.Photo.ExposureMode","ExposureMode",False),
("Exif.Photo.WhiteBalance","WhiteBalance",False),
("Exif.Photo.DigitalZoomRatio","DigitalZoomRatio",False),
("Exif.Photo.FocalLengthIn35mmFilm","FocalLengthIn35mmFilm",False),
("Exif.Photo.SceneCaptureType","SceneCaptureType",False),
("Exif.Photo.GainControl","GainControl",False),
("Exif.Photo.Contrast","Contrast",False),
("Exif.Photo.Saturation","Saturation",False),
("Exif.Photo.Sharpness","Sharpness",False),
("Exif.Photo.SubjectDistanceRange","SubjectDistanceRange",False),
("Exif.Image.Software","Software",False),
("Exif.Image.IPTCNAA","IPTCNAA",False),
("Exif.Photo.ImageUniqueID","ImageUniqueID",False),
("Exif.Image.ProcessingSoftware","Processing Software",False),
("Exif.GPSInfo.LatitudeRef","LatitudeRef",False),
("Exif.GPSInfo.Latitude","Latitude",False),
("Exif.GPSInfo.LongitudeRef","LongitudeRef",False),
("Exif.GPSInfo.Longitude","Longitude",False),
("Exif.GPSInfo.AltitudeRef","AltitudeRef",False),
("Exif.GPSInfo.Altitude","Altitude",False),
("Exif.GPSInfo.GPSTimeStamp","GPSTimeStamp",False),
)


'''
tags={
"Exif.Image.ProcessingSoftware":"Processing Software",
"Exif.Image.ImageWidth":"Width",
"Exif.Image.ImageLength":"Height",
"Exif.Image.DocumentName":"Document Name",
"Exif.Image.ImageDescription":"Image Description",
"Exif.Image.Make":"Make",
"Exif.Image.Model":"Model",
"Exif.Image.Orientation":"Orientation",
"Exif.Image.Software":"Software",
"Exif.Image.DateTime":"DateTime",
"Exif.Image.Artist":"Artist",
"Exif.Image.Copyright":"Copyright",
"Exif.Image.IPTCNAA":"IPTCNAA",
"Exif.Photo.ExposureTime":"Exposure Time",
"Exif.Photo.FNumber":"FNumber",
"Exif.Photo.ExposureProgram":"ExposureProgram",
"Exif.Photo.DateTimeOriginal":"DateTimeOriginal",
"Exif.Photo.ShutterSpeedValue":"ShutterSpeedValue",
"Exif.Photo.ApertureValue":"ApertureValue",
"Exif.Photo.BrightnessValue":"BrightnessValue",
"Exif.Photo.ExposureBiasValue":"ExposureBiasValue",
"Exif.Photo.MaxApertureValue":"MaxApertureValue",
"Exif.Photo.SubjectDistance":"SubjectDistance",
"Exif.Photo.MeteringMode":"MeteringMode",
"Exif.Photo.LightSource":"LightSource",
"Exif.Photo.Flash":"Flash",
"Exif.Photo.FocalLength":"FocalLength",
"Exif.Photo.SubjectArea":"SubjectArea",
"Exif.Photo.UserComment":"UserComment",
"Exif.Photo.RelatedSoundFile":"RelatedSoundFile",
"Exif.Photo.FlashEnergy":"FlashEnergy",
"Exif.Photo.SubjectLocation":"SubjectLocation",
"Exif.Photo.ExposureIndex":"ExposureIndex",
"Exif.Photo.SensingMethod":"SensingMethod",
"Exif.Photo.ExposureMode":"ExposureMode",
"Exif.Photo.WhiteBalance":"WhiteBalance",
"Exif.Photo.DigitalZoomRatio":"DigitalZoomRatio",
"Exif.Photo.FocalLengthIn35mmFilm":"FocalLengthIn35mmFilm",
"Exif.Photo.SceneCaptureType":"SceneCaptureType",
"Exif.Photo.GainControl":"GainControl",
"Exif.Photo.Contrast":"Contrast",
"Exif.Photo.Saturation":"Saturation",
"Exif.Photo.Sharpness":"Sharpness",
"Exif.Photo.SubjectDistanceRange":"SubjectDistanceRange",
"Exif.Photo.ImageUniqueID":"ImageUniqueID"
}
'''


'''
all_tags=(("Exif.Image.ProcessingSoftware","Ascii","The name and version of the software used to post-process the picture."),
("Exif.Image.NewSubfileType","Long","A general indication of the kind of data contained in this subfile."),
("Exif.Image.ImageWidth","Long","The number of columns of image data, equal to the number of pixels per row. In JPEG compressed data a JPEG marker is used instead of this tag."),
("Exif.Image.ImageLength","Long","The number of rows of image data. In JPEG compressed data a JPEG marker is used instead of this tag."),
("Exif.Image.BitsPerSample","Short","The number of bits per image component. In this standard each component of the image is 8 bits, so the value for this tag is 8. See also <SamplesPerPixel>. In JPEG compressed data a JPEG marker is used instead of this tag."),
("Exif.Image.Compression","Short","The compression scheme used for the image data. When a primary image is JPEG compressed, this designation is not necessary and is omitted. When thumbnails use JPEG compression, this tag value is set to 6."),
("Exif.Image.PhotometricInterpretation","Short","The pixel composition. In JPEG compressed data a JPEG marker is used instead of this tag."),
("Exif.Image.FillOrder","Short","The logical order of bits within a byte"),
("Exif.Image.DocumentName","Ascii","The name of the document from which this image was scanned"),
("Exif.Image.ImageDescription","Ascii","A character string giving the title of the image. It may be a comment such as '1988 company picnic' or the like. Two-bytes character codes cannot be used. When a 2-bytes code is necessary, the Exif Private tag <UserComment> is to be used."),
("Exif.Image.Make","Ascii","The manufacturer of the recording equipment. This is the manufacturer of the DSC, scanner, video digitizer or other equipment that generated the image. When the field is left blank, it is treated as unknown."),
("Exif.Image.Model","Ascii","The model name or model number of the equipment. This is the model name or number of the DSC, scanner, video digitizer or other equipment that generated the image. When the field is left blank, it is treated as unknown."),
("Exif.Image.StripOffsets","Long","For each strip, the byte offset of that strip. It is recommended that this be selected so the number of strip bytes does not exceed 64 Kbytes. With JPEG compressed data this designation is not needed and is omitted. See also <RowsPerStrip> and <StripByteCounts>."),
("Exif.Image.Orientation","Short","The image orientation viewed in terms of rows and columns."),
("Exif.Image.SamplesPerPixel","Short","The number of components per pixel. Since this standard applies to RGB and YCbCr images, the value set for this tag is 3. In JPEG compressed data a JPEG marker is used instead of this tag."),
("Exif.Image.RowsPerStrip","Long","The number of rows per strip. This is the number of rows in the image of one strip when an image is divided into strips. With JPEG compressed data this designation is not needed and is omitted. See also <StripOffsets> and <StripByteCounts>."),
("Exif.Image.StripByteCounts","Long","The total number of bytes in each strip. With JPEG compressed data this designation is not needed and is omitted."),
("Exif.Image.XResolution","Rational","The number of pixels per <ResolutionUnit> in the <ImageWidth> direction. When the image resolution is unknown, 72 [dpi] is designated."),
("Exif.Image.YResolution","Rational","The number of pixels per <ResolutionUnit> in the <ImageLength> direction. The same value as <XResolution> is designated."),
("Exif.Image.PlanarConfiguration","Short","Indicates whether pixel components are recorded in a chunky or planar format. In JPEG compressed files a JPEG marker is used instead of this tag. If this field does not exist, the TIFF default of 1 (chunky) is assumed."),
("Exif.Image.ResolutionUnit","Short","The unit for measuring <XResolution> and <YResolution>. The same unit is used for both <XResolution> and <YResolution>. If the image resolution is unknown, 2 (inches) is designated."),
("Exif.Image.TransferFunction","Short","A transfer function for the image, described in tabular style. Normally this tag is not necessary, since color space is specified in the color space information tag (<ColorSpace>)."),
("Exif.Image.Software","Ascii","This tag records the name and version of the software or firmware of the camera or image input device used to generate the image. The detailed format is not specified, but it is recommended that the example shown below be followed. When the field is left blank, it is treated as unknown."),
("Exif.Image.DateTime","Ascii","The date and time of image creation. In Exif standard, it is the date and time the file was changed."),
("Exif.Image.HostComputer","Ascii","This tag records information about the host computer used to generate the image."),
("Exif.Image.Artist","Ascii","This tag records the name of the camera owner, photographer or image creator. The detailed format is not specified, but it is recommended that the information be written as in the example below for ease of Interoperability. When the field is left blank, it is treated as unknown. Ex.) 'Camera owner, John Smith; Photographer, Michael Brown; Image creator, Ken James'"),
("Exif.Image.WhitePoint","Rational","The chromaticity of the white point of the image. Normally this tag is not necessary, since color space is specified in the colorspace information tag (<ColorSpace>)."),
("Exif.Image.PrimaryChromaticities","Rational","The chromaticity of the three primary colors of the image. Normally this tag is not necessary, since colorspace is specified in the colorspace information tag (<ColorSpace>)."),
("Exif.Image.TileWidth","Short","The tile width in pixels. This is the number of columns in each tile."),
("Exif.Image.TileLength","Short","The tile length (height) in pixels. This is the number of rows in each tile."),
("Exif.Image.TileOffsets","Short","For each tile, the byte offset of that tile, as compressed and stored on disk. The offset is specified with respect to the beginning of the TIFF file. Note that this implies that each tile has a location independent of the locations of other tiles."),
("Exif.Image.TileByteCounts","Short","For each tile, the number of (compressed) bytes in that tile. See TileOffsets for a description of how the byte counts are ordered."),
("Exif.Image.SubIFDs","Long","Defined by Adobe Corporation to enable TIFF Trees within a TIFF file."),
("Exif.Image.TransferRange","Short","Expands the range of the TransferFunction"),
("Exif.Image.JPEGProc","Long","This field indicates the process used to produce the compressed data"),
("Exif.Image.JPEGInterchangeFormat","Long","The offset to the start byte (SOI) of JPEG compressed thumbnail data. This is not used for primary image JPEG data."),
("Exif.Image.JPEGInterchangeFormatLength","Long","The number of bytes of JPEG compressed thumbnail data. This is not used for primary image JPEG data. JPEG thumbnails are not divided but are recorded as a continuous JPEG bitstream from SOI to EOI. Appn and COM markers should not be recorded. Compressed thumbnails must be recorded in no more than 64 Kbytes, including all other data to be recorded in APP1."),
("Exif.Image.YCbCrCoefficients","Rational","The matrix coefficients for transformation from RGB to YCbCr image data. No default is given in TIFF; but here the value given in Appendix E, 'Color Space Guidelines', is used as the default. The color space is declared in a color space information tag, with the default being the value that gives the optimal image characteristics Interoperability this condition."),
("Exif.Image.YCbCrSubSampling","Short","The sampling ratio of chrominance components in relation to the luminance component. In JPEG compressed data a JPEG marker is used instead of this tag."),
("Exif.Image.YCbCrPositioning","Short","The position of chrominance components in relation to the luminance component. This field is designated only for JPEG compressed data or uncompressed YCbCr data. The TIFF default is 1 (centered); but when Y:Cb:Cr = 4:2:2 it is recommended in this standard that 2 (co-sited) be used to record data, in order to improve the image quality when viewed on TV systems. When this field does not exist, the reader shall assume the TIFF default. In the case of Y:Cb:Cr = 4:2:0, the TIFF default (centered) is recommended. If the reader does not have the capability of supporting both kinds of <YCbCrPositioning>, it shall follow the TIFF default regardless of the value in this field. It is preferable that readers be able to support both centered and co-sited positioning."),
("Exif.Image.ReferenceBlackWhite","Rational","The reference black point value and reference white point value. No defaults are given in TIFF, but the values below are given as defaults here. The color space is declared in a color space information tag, with the default being the value that gives the optimal image characteristics Interoperability these conditions."),
("Exif.Image.XMLPacket","Byte","XMP Metadata (Adobe technote 9-14-02)"),
("Exif.Image.Rating","Short","Rating tag used by Windows"),
("Exif.Image.RatingPercent","Short","Rating tag used by Windows, value in percent"),
("Exif.Image.CFARepeatPatternDim","Short","Contains two values representing the minimum rows and columns to define the repeating patterns of the color filter array"),
("Exif.Image.CFAPattern","Byte","Indicates the color filter array (CFA) geometric pattern of the image sensor when a one-chip color area sensor is used. It does not apply to all sensing methods"),
("Exif.Image.BatteryLevel","Rational","Contains a value of the battery level as a fraction or string"),
("Exif.Image.IPTCNAA","Long","Contains an IPTC/NAA record"),
("Exif.Image.Copyright","Ascii","Copyright information. In this standard the tag is used to indicate both the photographer and editor copyrights. It is the copyright notice of the person or organization claiming rights to the image. The Interoperability copyright statement including date and rights should be written in this field; e.g., 'Copyright, John Smith, 19xx. All rights reserved.'. In this standard the field records both the photographer and editor copyrights, with each recorded in a separate part of the statement. When there is a clear distinction between the photographer and editor copyrights, these are to be written in the order of photographer followed by editor copyright, separated by NULL (in this case since the statement also ends with a NULL, there are two NULL codes). When only the photographer copyright is given, it is terminated by one NULL code . When only the editor copyright is given, the photographer copyright part consists of one space followed by a terminating NULL code, then the editor copyright is given. When the field is left blank, it is treated as unknown."),
("Exif.Image.ImageResources","Undefined","Contains information embedded by the Adobe Photoshop application"),
("Exif.Image.ExifTag","Long","A pointer to the Exif IFD. Interoperability, Exif IFD has the same structure as that of the IFD specified in TIFF. ordinarily, however, it does not contain image data as in the case of TIFF."),
("Exif.Image.InterColorProfile","Undefined","Contains an InterColor Consortium (ICC) format color space characterization/profile"),
("Exif.Image.GPSTag","Long","A pointer to the GPS Info IFD. The Interoperability structure of the GPS Info IFD, like that of Exif IFD, has no image data."),
("Exif.Image.TIFFEPStandardID","Byte","Contains four ASCII characters representing the TIFF/EP standard version of a TIFF/EP file, eg '1', '0', '0', '0'"),
("Exif.Image.XPTitle","Byte","Title tag used by Windows, encoded in UCS2"),
("Exif.Image.XPComment","Byte","Comment tag used by Windows, encoded in UCS2"),
("Exif.Image.XPAuthor","Byte","Author tag used by Windows, encoded in UCS2"),
("Exif.Image.XPKeywords","Byte","Keywords tag used by Windows, encoded in UCS2"),
("Exif.Image.XPSubject","Byte","Subject tag used by Windows, encoded in UCS2"),
("Exif.Image.PrintImageMatching","Undefined","Print Image Matching, descriptiont needed."),
("Exif.Image.DNGVersion","Byte","This tag encodes the DNG four-tier version number. For files compliant with version 1.1.0.0 of the DNG specification, this tag should contain the bytes: 1, 1, 0, 0."),
("Exif.Image.DNGBackwardVersion","Byte","This tag specifies the oldest version of the Digital Negative specification for which a file is compatible. Readers shouldnot attempt to read a file if this tag specifies a version number that is higher than the version number of the specification the reader was based on. In addition to checking the version tags, readers should, for all tags, check the types, counts, and values, to verify it is able to correctly read the file."),
("Exif.Image.UniqueCameraModel","Ascii","Defines a unique, non-localized name for the camera model that created the image in the raw file. This name should include the manufacturer's name to avoid conflicts, and should not be localized, even if the camera name itself is localized for different markets (see LocalizedCameraModel). This string may be used by reader software to index into per-model preferences and replacement profiles."),
("Exif.Image.LocalizedCameraModel","Byte","Similar to the UniqueCameraModel field, except the name can be localized for different markets to match the localization of the camera name."),
("Exif.Image.CFAPlaneColor","Byte","Provides a mapping between the values in the CFAPattern tag and the plane numbers in LinearRaw space. This is a required tag for non-RGB CFA images."),
("Exif.Image.CFALayout","Short","Describes the spatial layout of the CFA."),
("Exif.Image.LinearizationTable","Short","Describes a lookup table that maps stored values into linear values. This tag is typically used to increase compression ratios by storing the raw data in a non-linear, more visually uniform space with fewer total encoding levels. If SamplesPerPixel is not equal to one, this single table applies to all the samples for each pixel."),
("Exif.Image.BlackLevelRepeatDim","Short","Specifies repeat pattern size for the BlackLevel tag."),
("Exif.Image.BlackLevel","Rational","Specifies the zero light (a.k.a. thermal black or black current) encoding level, as a repeating pattern. The origin of this pattern is the top-left corner of the ActiveArea rectangle. The values are stored in row-column-sample scan order."),
("Exif.Image.BlackLevelDeltaH","SRational","If the zero light encoding level is a function of the image column, BlackLevelDeltaH specifies the difference between the zero light encoding level for each column and the baseline zero light encoding level. If SamplesPerPixel is not equal to one, this single table applies to all the samples for each pixel."),
("Exif.Image.BlackLevelDeltaV","SRational","If the zero light encoding level is a function of the image row, this tag specifies the difference between the zero light encoding level for each row and the baseline zero light encoding level. If SamplesPerPixel is not equal to one, this single table applies to all the samples for each pixel."),
("Exif.Image.WhiteLevel","Short","This tag specifies the fully saturated encoding level for the raw sample values. Saturation is caused either by the sensor itself becoming highly non-linear in response, or by the camera's analog to digital converter clipping."),
("Exif.Image.DefaultScale","Rational","DefaultScale is required for cameras with non-square pixels. It specifies the default scale factors for each direction to convert the image to square pixels. Typically these factors are selected to approximately preserve total pixel count. For CFA images that use CFALayout equal to 2, 3, 4, or 5, such as the Fujifilm SuperCCD, these two values should usually differ by a factor of 2.0."),
("Exif.Image.DefaultCropOrigin","Short","Raw images often store extra pixels around the edges of the final image. These extra pixels help prevent interpolation artifacts near the edges of the final image. DefaultCropOrigin specifies the origin of the final image area, in raw image coordinates (i.e., before the DefaultScale has been applied), relative to the top-left corner of the ActiveArea rectangle."),
("Exif.Image.DefaultCropSize","Short","Raw images often store extra pixels around the edges of the final image. These extra pixels help prevent interpolation artifacts near the edges of the final image. DefaultCropSize specifies the size of the final image area, in raw image coordinates (i.e., before the DefaultScale has been applied)."),
("Exif.Image.ColorMatrix1","SRational","ColorMatrix1 defines a transformation matrix that converts XYZ values to reference camera native color space values, under the first calibration illuminant. The matrix values are stored in row scan order. The ColorMatrix1 tag is required for all non-monochrome DNG files."),
("Exif.Image.ColorMatrix2","SRational","ColorMatrix2 defines a transformation matrix that converts XYZ values to reference camera native color space values, under the second calibration illuminant. The matrix values are stored in row scan order."),
("Exif.Image.CameraCalibration1","SRational","CameraClalibration1 defines a calibration matrix that transforms reference camera native space values to individual camera native space values under the first calibration illuminant. The matrix is stored in row scan order. This matrix is stored separately from the matrix specified by the ColorMatrix1 tag to allow raw converters to swap in replacement color matrices based on UniqueCameraModel tag, while still taking advantage of any per-individual camera calibration performed by the camera manufacturer."),
("Exif.Image.CameraCalibration2","SRational","CameraCalibration2 defines a calibration matrix that transforms reference camera native space values to individual camera native space values under the second calibration illuminant. The matrix is stored in row scan order. This matrix is stored separately from the matrix specified by the ColorMatrix2 tag to allow raw converters to swap in replacement color matrices based on UniqueCameraModel tag, while still taking advantage of any per-individual camera calibration performed by the camera manufacturer."),
("Exif.Image.ReductionMatrix1","SRational","ReductionMatrix1 defines a dimensionality reduction matrix for use as the first stage in converting color camera native space values to XYZ values, under the first calibration illuminant. This tag may only be used if ColorPlanes is greater than 3. The matrix is stored in row scan order."),
("Exif.Image.ReductionMatrix2","SRational","ReductionMatrix2 defines a dimensionality reduction matrix for use as the first stage in converting color camera native space values to XYZ values, under the second calibration illuminant. This tag may only be used if ColorPlanes is greater than 3. The matrix is stored in row scan order."),
("Exif.Image.AnalogBalance","Rational","Normally the stored raw values are not white balanced, since any digital white balancing will reduce the dynamic range of the final image if the user decides to later adjust the white balance; however, if camera hardware is capable of white balancing the color channels before the signal is digitized, it can improve the dynamic range of the final image. AnalogBalance defines the gain, either analog (recommended) or digital (not recommended) that has been applied the stored raw values."),
("Exif.Image.AsShotNeutral","Short","Specifies the selected white balance at time of capture, encoded as the coordinates of a perfectly neutral color in linear reference space values. The inclusion of this tag precludes the inclusion of the AsShotWhiteXY tag."),
("Exif.Image.AsShotWhiteXY","Rational","Specifies the selected white balance at time of capture, encoded as x-y chromaticity coordinates. The inclusion of this tag precludes the inclusion of the AsShotNeutral tag."),
("Exif.Image.BaselineExposure","SRational","Camera models vary in the trade-off they make between highlight headroom and shadow noise. Some leave a significant amount of highlight headroom during a normal exposure. This allows significant negative exposure compensation to be applied during raw conversion, but also means normal exposures will contain more shadow noise. Other models leave less headroom during normal exposures. This allows for less negative exposure compensation, but results in lower shadow noise for normal exposures. Because of these differences, a raw converter needs to vary the zero point of its exposure compensation control from model to model. BaselineExposure specifies by how much (in EV units) to move the zero point. Positive values result in brighter default results, while negative values result in darker default results."),
("Exif.Image.BaselineNoise","Rational","Specifies the relative noise level of the camera model at a baseline ISO value of 100, compared to a reference camera model. Since noise levels tend to vary approximately with the square root of the ISO value, a raw converter can use this value, combined with the current ISO, to estimate the relative noise level of the current image."),
("Exif.Image.BaselineSharpness","Rational","Specifies the relative amount of sharpening required for this camera model, compared to a reference camera model. Camera models vary in the strengths of their anti-aliasing filters. Cameras with weak or no filters require less sharpening than cameras with strong anti-aliasing filters."),
("Exif.Image.BayerGreenSplit","Long","Only applies to CFA images using a Bayer pattern filter array. This tag specifies, in arbitrary units, how closely the values of the green pixels in the blue/green rows track the values of the green pixels in the red/green rows. A value of zero means the two kinds of green pixels track closely, while a non-zero value means they sometimes diverge. The useful range for this tag is from 0 (no divergence) to about 5000 (quite large divergence)."),
("Exif.Image.LinearResponseLimit","Rational","Some sensors have an unpredictable non-linearity in their response as they near the upper limit of their encoding range. This non-linearity results in color shifts in the highlight areas of the resulting image unless the raw converter compensates for this effect. LinearResponseLimit specifies the fraction of the encoding range above which the response may become significantly non-linear."),
("Exif.Image.CameraSerialNumber","Ascii","CameraSerialNumber contains the serial number of the camera or camera body that captured the image."),
("Exif.Image.LensInfo","Rational","Contains information about the lens that captured the image. If the minimum f-stops are unknown, they should be encoded as 0/0."),
("Exif.Image.ChromaBlurRadius","Rational","ChromaBlurRadius provides a hint to the DNG reader about how much chroma blur should be applied to the image. If this tag is omitted, the reader will use its default amount of chroma blurring. Normally this tag is only included for non-CFA images, since the amount of chroma blur required for mosaic images is highly dependent on the de-mosaic algorithm, in which case the DNG reader's default value is likely optimized for its particular de-mosaic algorithm."),
("Exif.Image.AntiAliasStrength","Rational","Provides a hint to the DNG reader about how strong the camera's anti-alias filter is. A value of 0.0 means no anti-alias filter (i.e., the camera is prone to aliasing artifacts with some subjects), while a value of 1.0 means a strong anti-alias filter (i.e., the camera almost never has aliasing artifacts)."),
("Exif.Image.ShadowScale","SRational","This tag is used by Adobe Camera Raw to control the sensitivity of its 'Shadows' slider."),
("Exif.Image.DNGPrivateData","Byte","Provides a way for camera manufacturers to store private data in the DNG file for use by their own raw converters, and to have that data preserved by programs that edit DNG files."),
("Exif.Image.MakerNoteSafety","Short","MakerNoteSafety lets the DNG reader know whether the EXIF MakerNote tag is safe to preserve along with the rest of the EXIF data. File browsers and other image management software processing an image with a preserved MakerNote should be aware that any thumbnail image embedded in the MakerNote may be stale, and may not reflect the current state of the full size image."),
("Exif.Image.CalibrationIlluminant1","Short","The illuminant used for the first set of color calibration tags (ColorMatrix1, CameraCalibration1, ReductionMatrix1). The legal values for this tag are the same as the legal values for the LightSource EXIF tag."),
("Exif.Image.CalibrationIlluminant2","Short","The illuminant used for an optional second set of color calibration tags (ColorMatrix2, CameraCalibration2, ReductionMatrix2). The legal values for this tag are the same as the legal values for the CalibrationIlluminant1 tag; however, if both are included, neither is allowed to have a value of 0 (unknown)."),
("Exif.Image.BestQualityScale","Rational","For some cameras, the best possible image quality is not achieved by preserving the total pixel count during conversion. For example, Fujifilm SuperCCD images have maximum detail when their total pixel count is doubled. This tag specifies the amount by which the values of the DefaultScale tag need to be multiplied to achieve the best quality image size."),
("Exif.Image.RawDataUniqueID","Byte","This tag contains a 16-byte unique identifier for the raw image data in the DNG file. DNG readers can use this tag to recognize a particular raw image, even if the file's name or the metadata contained in the file has been changed. If a DNG writer creates such an identifier, it should do so using an algorithm that will ensure that it is very unlikely two different images will end up having the same identifier."),
("Exif.Image.OriginalRawFileName","Byte","If the DNG file was converted from a non-DNG raw file, then this tag contains the file name of that original raw file."),
("Exif.Image.OriginalRawFileData","Undefined","If the DNG file was converted from a non-DNG raw file, then this tag contains the compressed contents of that original raw file. The contents of this tag always use the big-endian byte order. The tag contains a sequence of data blocks. Future versions of the DNG specification may define additional data blocks, so DNG readers should ignore extra bytes when parsing this tag. DNG readers should also detect the case where data blocks are missing from the end of the sequence, and should assume a default value for all the missing blocks. There are no padding or alignment bytes between data blocks."),
("Exif.Image.ActiveArea","Short","This rectangle defines the active (non-masked) pixels of the sensor. The order of the rectangle coordinates is: top, left, bottom, right."),
("Exif.Image.MaskedAreas","Short","This tag contains a list of non-overlapping rectangle coordinates of fully masked pixels, which can be optionally used by DNG readers to measure the black encoding level. The order of each rectangle's coordinates is: top, left, bottom, right. If the raw image data has already had its black encoding level subtracted, then this tag should not be used, since the masked pixels are no longer useful."),
("Exif.Image.AsShotICCProfile","Undefined","This tag contains an ICC profile that, in conjunction with the AsShotPreProfileMatrix tag, provides the camera manufacturer with a way to specify a default color rendering from camera color space coordinates (linear reference values) into the ICC profile connection space. The ICC profile connection space is an output referred colorimetric space, whereas the other color calibration tags in DNG specify a conversion into a scene referred colorimetric space. This means that the rendering in this profile should include any desired tone and gamut mapping needed to convert between scene referred values and output referred values."),
("Exif.Image.AsShotPreProfileMatrix","SRational","This tag is used in conjunction with the AsShotICCProfile tag. It specifies a matrix that should be applied to the camera color space coordinates before processing the values through the ICC profile specified in the AsShotICCProfile tag. The matrix is stored in the row scan order. If ColorPlanes is greater than three, then this matrix can (but is not required to) reduce the dimensionality of the color data down to three components, in which case the AsShotICCProfile should have three rather than ColorPlanes input components."),
("Exif.Image.CurrentICCProfile","Undefined","This tag is used in conjunction with the CurrentPreProfileMatrix tag. The CurrentICCProfile and CurrentPreProfileMatrix tags have the same purpose and usage as the AsShotICCProfile and AsShotPreProfileMatrix tag pair, except they are for use by raw file editors rather than camera manufacturers."),
("Exif.Image.CurrentPreProfileMatrix","SRational","This tag is used in conjunction with the CurrentICCProfile tag. The CurrentICCProfile and CurrentPreProfileMatrix tags have the same purpose and usage as the AsShotICCProfile and AsShotPreProfileMatrix tag pair, except they are for use by raw file editors rather than camera manufacturers."),
("Exif","Exif.Photo.ExposureTime","Rational,Exposure time, given in seconds (sec)."),
("Exif","Exif.Photo.FNumber","Rational,The F number."),
("Exif","Exif.Photo.ExposureProgram","Short,The class of the program used by the camera to set exposure when the picture is taken."),
("Exif","Exif.Photo.SpectralSensitivity","Ascii,Indicates the spectral sensitivity of each channel of the camera used. The tag value is an ASCII string compatible with the standard developed by the ASTM Technical Committee."),
("Exif","Exif.Photo.ISOSpeedRatings","Short,Indicates the ISO Speed and ISO Latitude of the camera or input device as specified in ISO 12232."),
("Exif","Exif.Photo.OECF","Undefined,Indicates the Opto-Electoric Conversion Function (OECF) specified in ISO 14524. <OECF> is the relationship between the camera optical input and the image values."),
("Exif","Exif.Photo.ExifVersion","Undefined,The version of this standard supported. Nonexistence of this field is taken to mean nonconformance to the standard."),
("Exif","Exif.Photo.DateTimeOriginal","Ascii,The date and time when the original image data was generated. For a digital still camera the date and time the picture was taken are recorded."),
("Exif","Exif.Photo.DateTimeDigitized","Ascii,The date and time when the image was stored as digital data."),
("Exif","Exif.Photo.ComponentsConfiguration","Undefined,Information specific to compressed data. The channels of each component are arranged in order from the 1st component to the 4th. For uncompressed data the data arrangement is given in the <PhotometricInterpretation> tag. However, since <PhotometricInterpretation> can only express the order of Y, Cb and Cr, this tag is provided for cases when compressed data uses components other than Y, Cb, and Cr and to enable support of other sequences."),
("Exif","Exif.Photo.CompressedBitsPerPixel","Rational,Information specific to compressed data. The compression mode used for a compressed image is indicated in unit bits per pixel."),
("Exif","Exif.Photo.ShutterSpeedValue","SRational,Shutter speed. The unit is the APEX (Additive System of Photographic Exposure) setting."),
("Exif","Exif.Photo.ApertureValue","Rational,The lens aperture. The unit is the APEX value."),
("Exif","Exif.Photo.BrightnessValue","SRational,The value of brightness. The unit is the APEX value. Ordinarily it is given in the range of -99.99 to 99.99."),
("Exif","Exif.Photo.ExposureBiasValue","SRational,The exposure bias. The units is the APEX value. Ordinarily it is given in the range of -99.99 to 99.99."),
("Exif","Exif.Photo.MaxApertureValue","Rational,The smallest F number of the lens. The unit is the APEX value. Ordinarily it is given in the range of 00.00 to 99.99, but it is not limited to this range."),
("Exif","Exif.Photo.SubjectDistance","Rational,The distance to the subject, given in meters."),
("Exif","Exif.Photo.MeteringMode","Short,The metering mode."),
("Exif","Exif.Photo.LightSource","Short,The kind of light source."),
("Exif","Exif.Photo.Flash","Short,This tag is recorded when an image is taken using a strobe light (flash)."),
("Exif","Exif.Photo.FocalLength","Rational,The actual focal length of the lens, in mm. Conversion is not made to the focal length of a 35 mm film camera."),
("Exif","Exif.Photo.SubjectArea","Short,This tag indicates the location and area of the main subject in the overall scene."),
("Exif","Exif.Photo.MakerNote","Undefined,A tag for manufacturers of Exif writers to record any desired information. The contents are up to the manufacturer."),
("Exif","Exif.Photo.UserComment","Comment,A tag for Exif users to write keywords or comments on the image besides those in <ImageDescription>, and without the character code limitations of the <ImageDescription> tag."),
("Exif","Exif.Photo.SubSecTime","Ascii,A tag used to record fractions of seconds for the <DateTime> tag."),
("Exif","Exif.Photo.SubSecTimeOriginal","Ascii,A tag used to record fractions of seconds for the <DateTimeOriginal> tag."),
("Exif","Exif.Photo.SubSecTimeDigitized","Ascii,A tag used to record fractions of seconds for the <DateTimeDigitized> tag."),
("Exif","Exif.Photo.FlashpixVersion","Undefined,The FlashPix format version supported by a FPXR file."),
("Exif","Exif.Photo.ColorSpace","Short,The color space information tag is always recorded as the color space specifier. Normally sRGB is used to define the color space based on the PC monitor conditions and environment. If a color space other than sRGB is used, Uncalibrated is set. Image data recorded as Uncalibrated can be treated as sRGB when it is converted to FlashPix."),
("Exif","Exif.Photo.PixelXDimension","Long,Information specific to compressed data. When a compressed file is recorded, the valid width of the meaningful image must be recorded in this tag, whether or not there is padding data or a restart marker. This tag should not exist in an uncompressed file."),
("Exif","Exif.Photo.PixelYDimension","Long,Information specific to compressed data. When a compressed file is recorded, the valid height of the meaningful image must be recorded in this tag, whether or not there is padding data or a restart marker. This tag should not exist in an uncompressed file. Since data padding is unnecessary in the vertical direction, the number of lines recorded in this valid image height tag will in fact be the same as that recorded in the SOF."),
("Exif","Exif.Photo.RelatedSoundFile","Ascii,This tag is used to record the name of an audio file related to the image data. The only relational information recorded here is the Exif audio file name and extension (an ASCII string consisting of 8 characters + '.' + 3 characters). The path is not recorded."),
("Exif","Exif.Photo.InteroperabilityTag","Long,Interoperability IFD is composed of tags which stores the information to ensure the Interoperability and pointed by the following tag located in Exif IFD. The Interoperability structure of Interoperability IFD is the same as TIFF defined IFD structure but does not contain the image data characteristically compared with normal TIFF IFD."),
("Exif","Exif.Photo.FlashEnergy","Rational,Indicates the strobe energy at the time the image is captured, as measured in Beam Candle Power Seconds (BCPS)."),
("Exif","Exif.Photo.SpatialFrequencyResponse","Undefined,This tag records the camera or input device spatial frequency table and SFR values in the direction of image width, image height, and diagonal direction, as specified in ISO 12233."),
("Exif","Exif.Photo.FocalPlaneXResolution","Rational,Indicates the number of pixels in the image width (X) direction per <FocalPlaneResolutionUnit> on the camera focal plane."),
("Exif","Exif.Photo.FocalPlaneYResolution","Rational,Indicates the number of pixels in the image height (V) direction per <FocalPlaneResolutionUnit> on the camera focal plane."),
("Exif","Exif.Photo.FocalPlaneResolutionUnit","Short,Indicates the unit for measuring <FocalPlaneXResolution> and <FocalPlaneYResolution>. This value is the same as the <ResolutionUnit>."),
("Exif","Exif.Photo.SubjectLocation","Short,Indicates the location of the main subject in the scene. The value of this tag represents the pixel at the center of the main subject relative to the left edge, prior to rotation processing as per the <Rotation> tag. The first value indicates the X column number and second indicates the Y row number."),
("Exif","Exif.Photo.ExposureIndex","Rational,Indicates the exposure index selected on the camera or input device at the time the image is captured."),
("Exif","Exif.Photo.SensingMethod","Short,Indicates the image sensor type on the camera or input device."),
("Exif","Exif.Photo.FileSource","Undefined,Indicates the image source. If a DSC recorded the image, this tag value of this tag always be set to 3, indicating that the image was recorded on a DSC."),
("Exif","Exif.Photo.SceneType","Undefined,Indicates the type of scene. If a DSC recorded the image, this tag value must always be set to 1, indicating that the image was directly photographed."),
("Exif","Exif.Photo.CFAPattern","Undefined,Indicates the color filter array (CFA) geometric pattern of the image sensor when a one-chip color area sensor is used. It does not apply to all sensing methods."),
("Exif","Exif.Photo.CustomRendered","Short,This tag indicates the use of special processing on image data, such as rendering geared to output. When special processing is performed, the reader is expected to disable or minimize any further processing."),
("Exif","Exif.Photo.ExposureMode","Short,This tag indicates the exposure mode set when the image was shot. In auto-bracketing mode, the camera shoots a series of frames of the same scene at different exposure settings."),
("Exif","Exif.Photo.WhiteBalance","Short,This tag indicates the white balance mode set when the image was shot."),
("Exif","Exif.Photo.DigitalZoomRatio","Rational,This tag indicates the digital zoom ratio when the image was shot. If the numerator of the recorded value is 0, this indicates that digital zoom was not used."),
("Exif","Exif.Photo.FocalLengthIn35mmFilm","Short,This tag indicates the equivalent focal length assuming a 35mm film camera, in mm. A value of 0 means the focal length is unknown. Note that this tag differs from the <FocalLength> tag."),
("Exif","Exif.Photo.SceneCaptureType","Short,This tag indicates the type of scene that was shot. It can also be used to record the mode in which the image was shot. Note that this differs from the <SceneType> tag."),
("Exif","Exif.Photo.GainControl","Short,This tag indicates the degree of overall image gain adjustment."),
("Exif","Exif.Photo.Contrast","Short,This tag indicates the direction of contrast processing applied by the camera when the image was shot."),
("Exif","Exif.Photo.Saturation","Short,This tag indicates the direction of saturation processing applied by the camera when the image was shot."),
("Exif","Exif.Photo.Sharpness","Short,This tag indicates the direction of sharpness processing applied by the camera when the image was shot."),
("Exif","Exif.Photo.DeviceSettingDescription","Undefined,This tag indicates information on the picture-taking conditions of a particular camera model. The tag is used only to indicate the picture-taking conditions in the reader."),
("Exif","Exif.Photo.SubjectDistanceRange","Short,This tag indicates the distance to the subject."),
("Exif","Exif.Photo.ImageUniqueID","Ascii,This tag indicates an identifier assigned uniquely to each image. It is recorded as an ASCII string equivalent to hexadecimal notation and 128-bit fixed length."),
("Exif.Iop.InteroperabilityIndex","Ascii","Indicates the identification of the Interoperability rule. Use "R98" for stating ExifR98 Rules. Four bytes used including the termination code (NULL). see the separate volume of Recommended Exif Interoperability Rules (ExifR98) for other tags used for ExifR98."),
("Exif.Iop.InteroperabilityVersion","Undefined","Interoperability version"),
("Exif.Iop.RelatedImageFileFormat","Ascii","File format of image file"),
("Exif.Iop.RelatedImageWidth","Long","Image width"),
("Exif.Iop.RelatedImageLength","Long","Image height"))
'''
