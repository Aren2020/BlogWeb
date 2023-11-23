from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView
from django.core.paginator import Paginator,PageNotAnInteger,EmptyPage
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from .forms import EmailPostForm, CommentForm, SearchForm
from .models import Post, Comment

class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts' # default => post_list
    paginate_by = 3
    template_name = 'blog/post/list.html'

def post_list(request, tag_slug = None):
    posts = Post.published.all()

    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug = tag_slug)
        posts = posts.filter(tags__in = [tag])
                        
    paginator = Paginator(posts, 3) # 3 posts in one page
    page_number = request.GET.get('page', 1) # ?page=2
    posts = paginator.get_page(page_number)
    
    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    
    return render(request,
                  'blog/post/list.html',
                  {'posts': posts,
                   'tag': tag})
    
def post_detail(request, year, month, day, post_slug):
    post = get_object_or_404(Post,
                             status = Post.Status.PUBLISHED,
                             slug = post_slug, 
                             publish__year = year,
                             publish__month = month,
                             publish__day = day)

    comments = post.comments.filter(active = True)
    form = CommentForm()

    post_tags_ids = post.tags.values_list('id', flat = True)
    similar_posts = Post.published.filter(tags__in = post_tags_ids)\
                                  .exclude(id = post.id) # любое указонное совподение  
    similar_posts = similar_posts.annotate(same_tags = Count('tags'))\
                                 .order_by('-same_tags','-publish')[:4]

    return render(request,
                  'blog/post/detail.html',
                  {'post': post,
                   'comments': comments,
                   'form': form,
                   'similar_posts': similar_posts})

def post_share(request, post_id):
    post = get_object_or_404(Post,
                             id = post_id,
                             status = Post.Status.PUBLISHED)

    sent = False
    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(
                post.get_absolute_url()) # with these two i catch full url address of this post http://lo
            subject = f'{cd["name"]} recommends you read {post.title}'   
            message = f'Read {post.title} at {post_url}\n\n{cd["name"]}\'s comments: {cd["comment"]}'
        form = EmailPostForm()
        send_mail(subject, message, 'Aren.allahverdyan@gmail.com', [cd['to']])
        sent = True
    else:
        form = EmailPostForm()
    return render(request, 'blog/post/share.html', {'post':post,
                                                    'form':form,
                                                    'sent':sent})

@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(Post,
                             id = post_id,
                             status = Post.Status.PUBLISHED)
    comment = None
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit = False) # no save in db
        comment.post = post
        comment.save()
    return render(request, 'blog/post/comment.html',
                            {'post': post,
                             'form': form,
                             'comment': comment})

def post_search(request):
    form = SearchForm()
    query = None
    results = []

    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('title', weight='A') + SearchVector('body', weight='B')
            search_query = SearchQuery(query)
            results = Post.published.annotate(
                                rank = SearchRank(search_vector, search_query)
            ).filter(rank__gte = 0.3).order_by('-rank')

    return render(request,
                  'blog/post/search.html',
                  {'form': form,
                   'query': query,
                   'results': results})