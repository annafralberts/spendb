'''
This module implements views on the database.
'''
import logging
from collections import defaultdict
from datetime import datetime
from pylons import config

from openspending.model import Dataset
from openspending.ui.lib.cache import AggregationCache
from openspending.lib.jsonexport import to_json
from openspending.ui.lib import widgets

log = logging.getLogger(__name__)


class View(object):

    def __init__(self, dataset, view):
        self.dataset = dataset
        self.config = view
        self.entity = view.get('entity').lower().strip()
        self.filters = view.get('filters', {})
        if self.entity == 'entity':
            self.filters['taxonomy'] = 'entity'
        self.name = view.get('name')
        self.label = view.get('label')
        self.dimension = view.get('dimension')
        self.drilldown = view.get('drilldown',
                                  view.get('breakdown'))
        self.cuts = view.get('cuts',
                             view.get('view_filters', {}))

    def match(self, obj, dimension=None):
        if isinstance(obj, Dataset):
            return self.entity == 'dataset'
        if self.dimension != dimension:
            return False
        for k, v in self.filters.items():
            if obj.get(k) != v:
                return False
        return True

    @classmethod
    def by_name(cls, dataset, obj, name, dimension=None):
        """get a``View`` with the name ``name`` from the object

        ``obj``
            a model object (instance of :class:`openspending.model.Base`)
        ``name``
            The name of the ``View``

        returns: An instance of :class:`View` if the view could
        be found.

        raises: ``ValueError`` if the view does not exist.
        """
        for data in dataset.data.get('views', []):
            view = cls(dataset, data)
            if view.name == name and view.match(obj, dimension):
                return view
        raise ValueError("View %s does not exist." % name)

    @classmethod
    def available(cls, dataset, obj, dimension=None):
        views = []
        for data in dataset.data.get('views', []):
            view = View(dataset, data)
            if view.match(obj, dimension):
                views.append(view)
        return views

    @property
    def vis_state(self):
        return {
            'drilldown': self.drilldown,
            'cuts': self.cuts
            }

    @property
    def vis_widget(self):
        return widgets.get_widget('treemap')

    @property
    def table_state(self):
        return {
            'drilldowns': [self.drilldown],
            'cuts': self.cuts
            }

    @property
    def table_widget(self):
        return widgets.get_widget('aggregate_table')


def _set_time_context(request, c):
    # TODO: this is an unholy mess that needs to be killed
    # with fire.
    req_time = request.params.get('_time')
    c.times = [m['year'] for m in c.dataset['time'].members()]
    c.times = list(set(c.times))
    if req_time in c.times:
        c.state['time'] = req_time
    c.time = c.state.get('time')
    if c.time not in c.times and len(c.times):
        current_year = str(datetime.utcnow().year)
        if c.dataset.default_time:
            c.time = c.dataset.default_time
        elif current_year in c.times:
            c.time = current_year
        else:
            c.time = c.times[-1]
    # TODO: more clever way to set comparison time
    c.time_before = None
    if c.time and c.time in c.times:
        c.time_before = c.times[c.times.index(c.time) - 1]


def handle_request(request, c, obj, dimension=None):
    view_name = request.params.get('_view', 'default')
    c.available_views = View.available(c.dataset, obj, dimension)
    try:
        c.view = View.by_name(c.dataset, obj, view_name,
                              dimension=dimension)
    except ValueError:
        c.view = None
        return

    _set_time_context(request, c)
