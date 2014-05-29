from five import grok
from nuw.types import Base
from OFS.SimpleItem import SimpleItem
from PIL import Image, ImageDraw
from Products.CMFCore.utils import UniqueObject, getToolByName
from sqlalchemy import Column, Integer, Sequence, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from StringIO import StringIO
from z3c.saconfig import named_scoped_session
from zope.interface import Interface, implements

import uuid

grok.templatedir( 'templates' )
Session = named_scoped_session('nuw.types')

MAXSIZE = 1000 # The max width/height an image can have


class DBImage( Base ):
    __tablename__ = 'image'
    
    id = Column( Integer, Sequence( 'image_id' ), primary_key = True )
    imageid = Column( UUID )
    width = Column( Integer )
    height = Column( Integer )
    data = Column( LargeBinary )

class IImageStoreTool( Interface ):
    pass

class ImageStoreTool( UniqueObject, SimpleItem ):
    implements( IImageStoreTool )
    
    id = 'image_store'
    meta_type = 'NUW DB Image Store'
    plone_tool = 1
    
    def __getitem__( self, name ):
        ret = ImageLoader( self, name )
        ret.__parent__ = self
        ret._id = name
        
        return ret
    
    def add_image( self, imfile, imageid = None ):
        sess = Session()
        imfile.seek( 0 )
        im = Image.open( imfile )
        im = im.convert( 'RGB' )
        
        # Make sure the image is not too big.
        if im.size[0] > MAXSIZE or im.size[1] > MAXSIZE:
            im.thumbnail( ( MAXSIZE, MAXSIZE ), Image.BICUBIC )

        imfile = StringIO()
        im.save( imfile, 'JPEG' )
        
        if not imageid:
            imageid = str( uuid.uuid4() )
        
        imfile.seek(0)
        sess.add( DBImage( imageid = imageid, width = im.size[0], height = im.size[1], data = imfile.read() ) )
        
        return imageid, im.size[0], im.size[1]
    
    def get_image( self, imid, width = None ):
        sess = Session()
        
        q = sess.query( DBImage ).filter( DBImage.imageid == imid )
        
        if width:
            q = q.filter( DBImage.width == width )
        
        img = q.order_by( DBImage.width.desc() ).first()
        
        if img:
            return StringIO( img.data )
        elif width:
            # Nothing found with width set, check if there is an original and resize it save and return it
            img = sess.query( DBImage ).filter( DBImage.imageid == imid ).order_by( DBImage.width.desc() ).first()
            
            if img:
                im = StringIO( img.data )
                im = Image.open( im )
                
                w,h = im.size
                
                # Make sure original is bigger than the requested width
                if w > width:
                    # Calc height to not distort aspect ratios
                    height = int( h * ( float( width ) / float( w ) ) )
                    
                    im = im.resize( ( width, height ), Image.BICUBIC )
                    
                    buf = StringIO()
                    im.save( buf, 'JPEG' )
                    
                    self.add_image( buf, img.imageid )
                else:
                    buf = StringIO()
                    im.save( buf, 'JPEG' )

                return buf

class ImageLoader( SimpleItem ):
    def __init__( self, store, name ):
        self.store = store
        self.name = name

        if self.name.endswith( '.jpeg' ):
            self.name = self.name[:-5]
    
    def __call__( self ):
        self.store.REQUEST.response.setHeader( 'Content-type', 'image/jpeg' )
        
        name = self.name.split( '_' )
        if len( name ) > 1:
            imid = name[0]
            width = int( name[1] )
        else:
            imid = name[0]
            width = None

        imfile = self.store.get_image( imid, width )
        
        if not imfile:
            raise KeyError, 'Could not find image'

        return imfile.getvalue()
        
class ImageUploader( grok.View ):
    grok.context( Interface )
    grok.require( "cmf.ManagePortal" )
    
    def update( self ):
        self.lastimageuuid = None
        if self.request.form:
            if self.request.form[ 'image' ]:
                store = getToolByName( self.context, 'image_store' )
                
                self.lastimageuuid = store.add_image( self.request.form[ 'image' ] )[0]
