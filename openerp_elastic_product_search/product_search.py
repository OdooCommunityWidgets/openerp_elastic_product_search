# -*- coding: utf-8 -*-

from osv import fields, osv
from pyes import ES
import pyes.exceptions
import tools
import logging

_logger = logging.getLogger(__name__)

server = tools.config.get('elasticsearch', '127.0.0.1:9200')
conn = ES(server)
_logger.info('Connecting to ElasticSearch server %s' % server)

# FIXME: it would be ideal if we could configure the
# classes and fields we're interested in.


class search_mixin(osv.osv):

    _register = False

    def write(self, cr, user, ids, vals, context=None):
        success = super(search_mixin, self).write(cr, user, ids,
                                                    vals, context)
        if success and ids:
            data = self._filter_values(vals)
            if len(data) > 0:
                if isinstance(ids, (int, long)):
                    ids = [ids]
                index = self._index_name(cr)
                for prod_id in ids:
                    try:
                        conn.update(data, index, self.search_type, prod_id)
                    except pyes.exceptions.IndexMissingException:
                        # may as well just index what we have.
                        # NOTE: this isn't the only time we might create
                        # the index, it's just the only time we explicitly
                        # notice we are.
                        _logger.info('Creating index %s in ElasticSearch'
                                        % index)
                        conn.index(data, index, self.search_type, prod_id)
                    except pyes.exceptions.NotFoundException:
                        # may as well just index what we have.
                        _logger.debug('%s %d not found in index'
                                        % (self.search_type, prod_id))
                        conn.index(data, index, self.search_type, prod_id)

        return success

    def create(self, cr, user, vals, context=None):
        o = super(search_mixin, self).create(cr, user, vals, context)
        if o:
            data = self._filter_values(vals)
            if len(data) > 0:
                index = self._index_name(cr)
                conn.index(data, index, self.search_type, o)
        return o

    def unlink(self, cr, uid, ids, context=None):
        success = super(search_mixin, self).unlink(cr, uid, ids, context)
        if success and ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            index = self._index_name(cr)
            for prod_id in ids:
                conn.delete(index, self.search_type, prod_id)
        return success

    def _filter_values(self, vals):
        return dict([isinstance(v[1], tuple) and (v[0], v[1][0]) or v
                        for v in vals.items()
                        if v[0] in self.columns_to_search])

    def _index_name(self, cr):
        # FIXME how safe is the dbname for this purpose?
        index = "openerp_" + cr.dbname
        return index

    def reindex(self, cr, uid):
        prod_ids = self.search(cr, uid, [])
        # FIXME: is reading all the products in one go a good idea?
        # perhaps break it into chunks?
        prods = self.read(cr, uid, prod_ids)
        # FIXME: also think about making use of the elastic search
        # bulk operations
        index = self._index_name(cr)
        for product in prods:
            data = self._filter_values(product)
            if len(data) > 0:
                _logger.debug("%s: Indexing %s %d" %
                            (index, self.search_type, product['id']))
                _logger.debug(data)
                conn.index(data, index, self.search_type, product['id'])


class product_template_search(search_mixin):
    _name = "product.template"
    _inherit = "product.template"
    _register = True

    columns_to_search = ['description', 'description_sale',
                            'name', 'categ_id']
    search_type = 'product_template'


class product_search(search_mixin):
    _name = "product.product"
    _inherit = "product.product"
    _register = True

    columns_to_search = ['description', 'description_sale',
                            'name', 'categ_id']
    search_type = 'product'


class product_category_search(search_mixin):

    _name = 'product.category'
    _inherit = 'product.category'
    # FIXME: need to change name we store it as.
    columns_to_search = ['name']
    search_type = 'product_category'

product_template_search()
product_search()
